package src

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"mime/multipart"
	"net/http"
	"os"
	"strings"
	// "path/filepath"

	"github.com/gorilla/websocket"
	"github.com/sashabaranov/go-openai"

	"callbot_go/config"
)

// AudioSegment represents an audio segment with its data
type AudioSegment struct {
	Data []byte
}

// SpeechProcessor handles speech-to-text and text-to-speech conversions
type SpeechProcessor struct {
	// Only keeping OpenAIClient since other fields can be accessed from config
	OpenAIClient *openai.Client
}

// NewSpeechProcessor creates a new SpeechProcessor instance
func NewSpeechProcessor() *SpeechProcessor {
	cfg := config.GetConfig()
	
	var openaiClient *openai.Client
	
	// Kiểm tra xem API Key có tồn tại không trước khi tạo client
	if cfg.OpenAIAPIKey == "" {
		log.Println("ERROR: OpenAI API Key is empty. Speech-to-text and text-to-speech functions will not work correctly.")
	} else {
		log.Printf("Initializing OpenAI client with API key (length: %d)", len(cfg.OpenAIAPIKey))
		if len(cfg.OpenAIAPIKey) > 10 {
			log.Printf("API key prefix: %s...", cfg.OpenAIAPIKey[:10])
		}
		openaiClient = openai.NewClient(cfg.OpenAIAPIKey)
	}
	
	return &SpeechProcessor{
		OpenAIClient: openaiClient,
	}
}

// SpeechToText converts audio data to text
func (sp *SpeechProcessor) SpeechToText(audioData []byte) (string, error) {
	cfg := config.GetConfig()
	
	if cfg.STTProvider == "local" {
		return sp.localSpeechToText(audioData)
	} else {
		return sp.openaiSpeechToText(audioData)
	}
}

// localSpeechToText converts audio data to text using a local API
func (sp *SpeechProcessor) localSpeechToText(audioData []byte) (string, error) {
	cfg := config.GetConfig()
	
	// Create temporary WAV file
	tempFile, err := ioutil.TempFile("", "audio_*.wav")
	if err != nil {
		return "", fmt.Errorf("error creating temporary file: %v", err)
	}
	defer os.Remove(tempFile.Name())
	defer tempFile.Close()
	
	// Write audio data to the file
	// In a real implementation, you would convert the raw audio data to WAV format
	// This is a simplified version
	_, err = tempFile.Write(audioData)
	if err != nil {
		return "", fmt.Errorf("error writing to temporary file: %v", err)
	}
	
	// Reset file pointer
	tempFile.Seek(0, 0)
	
	// Create a multipart form request
	var requestBody bytes.Buffer
	writer := multipart.NewWriter(&requestBody)
	
	// Add file to form
	fileWriter, err := writer.CreateFormFile("file", "audio.wav")
	if err != nil {
		return "", fmt.Errorf("error creating form file: %v", err)
	}
	
	// Copy file content to form
	_, err = io.Copy(fileWriter, tempFile)
	if err != nil {
		return "", fmt.Errorf("error copying file to form: %v", err)
	}
	
	// Close multipart writer
	writer.Close()
	
	// Create HTTP request
	request, err := http.NewRequest("POST", cfg.STTApiURL, &requestBody)
	if err != nil {
		return "", fmt.Errorf("error creating request: %v", err)
	}
	
	request.Header.Set("Content-Type", writer.FormDataContentType())
	
	// Send request
	client := &http.Client{}
	response, err := client.Do(request)
	if err != nil {
		return "", fmt.Errorf("error sending request: %v", err)
	}
	defer response.Body.Close()
	
	// Read response
	responseBody, err := ioutil.ReadAll(response.Body)
	if err != nil {
		return "", fmt.Errorf("error reading response: %v", err)
	}
	
	// Check status code
	if response.StatusCode != 200 {
		return "", fmt.Errorf("error from API: %s", responseBody)
	}
	
	// Parse JSON response
	var result map[string]interface{}
	err = json.Unmarshal(responseBody, &result)
	if err != nil {
		return "", fmt.Errorf("error parsing response: %v", err)
	}
	
	// Extract transcription
	transcription, ok := result["transcription"].(string)
	if !ok {
		return "", fmt.Errorf("transcription not found in response")
	}
	
	return transcription, nil
}

// openaiSpeechToText converts audio data to text using OpenAI's API
func (sp *SpeechProcessor) openaiSpeechToText(audioData []byte) (string, error) {
	if sp.OpenAIClient == nil {
		return "", fmt.Errorf("OpenAI client not initialized. Please check your API key")
	}
	
	cfg := config.GetConfig()
	
	// Create temporary WAV file
	tempFile, err := ioutil.TempFile("", "audio_*.wav")
	if err != nil {
		return "", fmt.Errorf("error creating temporary file: %v", err)
	}
	
	// Print temp file name for debugging
	fmt.Println("===============")
	fmt.Println(tempFile.Name())
	fmt.Println("===============")
	
	defer os.Remove(tempFile.Name())
	
	// Write audio data to file
	_, err = tempFile.Write(audioData)
	if err != nil {
		tempFile.Close()
		return "", fmt.Errorf("error writing to temporary file: %v", err)
	}
	
	tempFile.Close()
	
	// Create transcription request
	req := openai.AudioRequest{
		Model:    cfg.STTModel,
		FilePath: tempFile.Name(),
		Language: cfg.STTLanguage,
	}
	
	// Create context
	ctx := context.Background()
	
	// Make transcription request with context
	resp, err := sp.OpenAIClient.CreateTranscription(ctx, req)
	if err != nil {
		return "", fmt.Errorf("error with OpenAI transcription: %v", err)
	}
	
	return resp.Text, nil
}

// TextToSpeech converts text to speech
func (sp *SpeechProcessor) TextToSpeech(text string, uuid string) (*AudioSegment, error) {
	cfg := config.GetConfig()
	
	if cfg.TTSProvider == "openai" {
		return sp.openaiTTS(text)
	} else if cfg.TTSProvider == "local" {
		return sp.localTTS(text)
	}
	
	return nil, fmt.Errorf("unknown TTS provider: %s", cfg.TTSProvider)
}

// getOpenAISpeechVoice converts a string voice name to the appropriate OpenAI SpeechVoice enum
func getOpenAISpeechVoice(voiceName string) openai.SpeechVoice {
	voiceName = strings.ToLower(voiceName)
	
	switch voiceName {
	case "alloy":
		return openai.VoiceAlloy
	case "echo":
		return openai.VoiceEcho
	case "fable":
		return openai.VoiceFable
	case "onyx":
		return openai.VoiceOnyx
	case "nova":
		return openai.VoiceNova
	case "shimmer":
		return openai.VoiceShimmer
	default:
		// Default to Alloy if voice isn't recognized
		log.Printf("Warning: Unrecognized voice '%s', defaulting to 'alloy'", voiceName)
		return openai.VoiceAlloy
	}
}

// openaiTTS converts text to speech using OpenAI's API
func (sp *SpeechProcessor) openaiTTS(text string) (*AudioSegment, error) {
	if sp.OpenAIClient == nil {
		return nil, fmt.Errorf("OpenAI client not initialized. Please check your API key")
	}
	
	cfg := config.GetConfig()
	
	// Create context
	ctx := context.Background()
	
	// Convert string voice name to OpenAI SpeechVoice enum
	voice := getOpenAISpeechVoice(cfg.TTSOpenAIVoice)
	
	// Create speech request with the correct struct and voice enum
	req := openai.CreateSpeechRequest{
		Model: "tts-1",
		Voice: voice,
		Input: text,
	}
	
	// Send request with context
	resp, err := sp.OpenAIClient.CreateSpeech(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("error with OpenAI TTS: %v", err)
	}
	
	// Read the response body
	audioBytes, err := io.ReadAll(resp)
	if err != nil {
		return nil, fmt.Errorf("error reading response body: %v", err)
	}
	defer resp.Close()
	
	// Return audio segment
	return &AudioSegment{Data: audioBytes}, nil
}

// localTTS converts text to speech using local websocket service
func (sp *SpeechProcessor) localTTS(text string) (*AudioSegment, error) {
	cfg := config.GetConfig()
	
	// Connect to websocket
	conn, _, err := websocket.DefaultDialer.Dial(cfg.TTSWebsocketURL, nil)
	if err != nil {
		return nil, fmt.Errorf("error connecting to TTS websocket: %v", err)
	}
	defer conn.Close()
	
	// Create request
	request := map[string]string{
		"text": text,
		"language": cfg.TTSLanguage,
		"sample_file": cfg.TTSVoice,
	}
	
	// Send request
	err = conn.WriteJSON(request)
	if err != nil {
		return nil, fmt.Errorf("error sending request to TTS websocket: %v", err)
	}
	
	// Process response
	combinedAudio := []byte{}
	
	for {
		// Read message
		_, message, err := conn.ReadMessage()
		if err != nil {
			return nil, fmt.Errorf("error reading from TTS websocket: %v", err)
		}
		
		// Parse response
		var data map[string]interface{}
		err = json.Unmarshal(message, &data)
		if err != nil {
			return nil, fmt.Errorf("error parsing TTS response: %v", err)
		}
		
		// Check for error
		if errorMsg, ok := data["error"].(string); ok {
			log.Printf("TTS Error: %s", errorMsg)
			continue
		}
		
		// Process audio data
		if audioBase64, ok := data["audio_base64"].(string); ok {
			// Decode base64 data
			audioBytes, err := base64.StdEncoding.DecodeString(audioBase64)
			if err != nil {
				return nil, fmt.Errorf("error decoding audio: %v", err)
			}
			
			// Append to combined audio
			combinedAudio = append(combinedAudio, audioBytes...)
		}
		
		// Check if this is the last message
		index, _ := data["index"].(float64)
		total, _ := data["total"].(float64)
		
		if int(index) == int(total) - 1 {
			break
		}
	}
	
	return &AudioSegment{Data: combinedAudio}, nil
} 