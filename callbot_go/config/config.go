package config 
// package main

import (
	"os"
	// "path/filepath"
	"log"
	"fmt"
	"github.com/joho/godotenv"
)

type Config struct {
	// API Endpoints
	TTSWebsocketURL string
	STTApiURL       string

	// Audio Settings
	AudioChunk          int
	AudioFormat         string
	AudioChannels       int
	AudioRate           int
	SilenceThreshold    int
	SilenceChunks       int
	InitialSilenceChunks int
	MaxConversationTime  int

	// Text-to-Speech Settings
	TTSProvider      string
	TTSVoice         string
	TTSOpenAIVoice   string
	TTSLanguage      string

	// Speech-to-Text Settings
	STTProvider   string
	STTLanguage   string
	STTModel      string

	// Chatbot Settings
	EndConversationKeywords []string

	// OpenAI config
	GPTModel      string
	OpenAIAPIKey  string

	// Dify config
	DifyAPIURL  string
	DifyAPIKey  string

	// Bot type configuration
	BotType     string
	LocalLLMURL string

	// RTP Settings
	RTPLocalIP string

	// Port settings
	UserPort int
	BotPort  int
}

var cfg *Config

// loadEnvFromPaths tries to load .env file from multiple paths
func loadEnvFromPaths() {
	// Các đường dẫn có thể chứa file .env
	paths := []string{
		// ".env",                   // Thư mục hiện tại
		// "../.env",                // Thư mục cha
		// "config/.env",            // Thư mục config
		"../config/.env",         // Thư mục config từ thư mục cha
		// "callbot_go/config/.env", // Đường dẫn tuyệt đối từ workspace
	}

	envLoaded := false
	
	// In thư mục hiện tại để debug
	dir, _ := os.Getwd()
	log.Printf("Current directory: %s", dir)

	// Thử load từ từng đường dẫn
	for _, path := range paths {
		err := godotenv.Load(path)
		if err == nil {
			log.Printf("Loaded .env from %s", path)
			envLoaded = true
			break // Nếu đã load được thì dừng
		} else {
			log.Printf("Could not load .env from %s: %v", path, err)
		}
	}

	if !envLoaded {
		// Biện pháp cuối cùng - hardcode giá trị API key vào biến môi trường
		log.Println("Failed to load any .env file, setting OPENAI_API_KEY directly")
		os.Setenv("OPENAI_API_KEY", "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")
	}
}

func GetConfig() *Config {
	if cfg != nil {
		return cfg
	}

	// Thử tải .env từ nhiều vị trí
	loadEnvFromPaths()

	// Logging để debug - kiểm tra xem đã load được OPENAI_API_KEY chưa
	if os.Getenv("OPENAI_API_KEY") != "" {
		log.Println("OPENAI_API_KEY is set with length:", len(os.Getenv("OPENAI_API_KEY")))
	} else {
		log.Println("Warning: OPENAI_API_KEY is not set")
	}

	cfg = &Config{
		TTSWebsocketURL: "ws://t2s.vts-dasc.net/ws/generate_speech/",
		STTApiURL:       "https://asr.vts-dasc.net/asr/upload/?en=false",

		AudioChunk:           1024,
		AudioFormat:          "paInt16",
		AudioChannels:        1,
		AudioRate:            8000,
		SilenceThreshold:     300,
		SilenceChunks:        60,
		InitialSilenceChunks: 80,
		MaxConversationTime:  300,

		TTSProvider:    getEnvOrDefault("TTS_PROVIDER", "openai"),
		TTSVoice:       "nam-calm.wav",
		TTSOpenAIVoice: "alloy",
		TTSLanguage:    "vi",

		STTProvider: getEnvOrDefault("STT_PROVIDER", "openai"),
		STTLanguage: "vi",
		STTModel:    "whisper-1",

		EndConversationKeywords: []string{"tạm biệt", "goodbye", "bye", "kết thúc"},

		GPTModel:     "gpt-4o-mini",
		OpenAIAPIKey: os.Getenv("OPENAI_API_KEY"),

		DifyAPIURL: getEnvOrDefault("DIFY_API_URL", "http://34.174.214.130:8088/v1/chat-messages"),
		DifyAPIKey: getEnvOrDefault("DIFY_API_KEY", "app-jEAZXlZZVZpdpximRcwqKafz"),

		BotType:     getEnvOrDefault("BOT_TYPE", "openai"),
		LocalLLMURL: "https://llm.vts-dasc.net/test",

		RTPLocalIP: getEnvOrDefault("RTP_LOCAL_IP", "127.0.0.1"),

		UserPort: 5060,
		BotPort:  5006,
	}

	// Double check OPENAI_API_KEY đã được set trong config
	if cfg.OpenAIAPIKey == "" {
		log.Println("WARNING: OpenAIAPIKey still empty in config after env loading!")
		// Biện pháp cuối cùng - hardcode API key trực tiếp vào config
		cfg.OpenAIAPIKey = "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"
	}

	return cfg
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
} 

func main() {
	cfg := GetConfig()
	fmt.Println(cfg)
}