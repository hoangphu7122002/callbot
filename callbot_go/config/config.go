package config 

import (
	"os"

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

func GetConfig() *Config {
	if cfg != nil {
		return cfg
	}

	_ = godotenv.Load()

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

	return cfg
}

func getEnvOrDefault(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
} 