package test

import (
	"callbot_go/config"
	"callbot_go/src"
	"io/ioutil"
	"log"
	"os"
	"strings"
	"testing"
	"unicode"
)

// Hàm chuyển đổi text thành dạng không dấu, viết thường
func normalizeVietnameseText(input string) string {
	// Bảng chuyển đổi các ký tự có dấu sang không dấu
	var pairs = map[rune]rune{
		'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
		'ă': 'a', 'ằ': 'a', 'ắ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
		'â': 'a', 'ầ': 'a', 'ấ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
		'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
		'ê': 'e', 'ề': 'e', 'ế': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
		'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
		'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
		'ô': 'o', 'ồ': 'o', 'ố': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
		'ơ': 'o', 'ờ': 'o', 'ớ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
		'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
		'ư': 'u', 'ừ': 'u', 'ứ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
		'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
		'đ': 'd',
	}

	// Chuyển đổi thành chữ thường và loại bỏ dấu
	result := ""
	for _, c := range strings.ToLower(input) {
		if replacement, ok := pairs[c]; ok {
			result += string(replacement)
		} else if unicode.IsLetter(c) || unicode.IsDigit(c) || c == ' ' {
			result += string(c)
		}
	}
	
	return result
}

// Hàm lấy các từ khóa từ một câu
func extractKeywords(text string) []string {
	normalized := normalizeVietnameseText(text)
	words := strings.Fields(normalized) // Tách chuỗi theo khoảng trắng
	
	// Bỏ qua các từ quá ngắn và các từ nối
	var keywords []string
	for _, word := range words {
		if len(word) >= 2 && word != "la" && word != "va" && word != "cua" && word != "toi" {
			keywords = append(keywords, word)
		}
	}
	
	return keywords
}

// TestNewSpeechProcessor tests creating a new SpeechProcessor instance
func TestNewSpeechProcessor(t *testing.T) {
	// Đảm bảo config đã được khởi tạo đúng
	cfg := config.GetConfig()
	
	// Log thông tin API key để debug
	log.Printf("OpenAI API Key in config (length): %d", len(cfg.OpenAIAPIKey))
	if len(cfg.OpenAIAPIKey) > 10 {
		log.Printf("API key prefix: %s...", cfg.OpenAIAPIKey[:10])
	}
	
	// Kiểm tra xem API key có được set đúng không
	if cfg.OpenAIAPIKey == "" {
		t.Logf("WARNING: OpenAI API Key is empty! Some tests will be skipped.")
	}
	
	processor := src.NewSpeechProcessor()
	
	if processor == nil {
		t.Fatalf("Expected non-nil processor")
	}
	
	// Kiểm tra xem client có được khởi tạo không nếu API key được set
	if cfg.OpenAIAPIKey != "" && processor.OpenAIClient == nil {
		t.Errorf("OpenAI client not initialized despite API key being set")
	}
}

// TestTextToSpeechOpenAI tests the OpenAI text-to-speech functionality
func TestTextToSpeechOpenAI(t *testing.T) {
	// Check if OPENAI_API_KEY is set
	cfg := config.GetConfig()
	
	// Log để debug
	log.Printf("OpenAI API Key in TextToSpeech test (length): %d", len(cfg.OpenAIAPIKey))
	
	if cfg.OpenAIAPIKey == "" {
		t.Skip("Skipping test because OPENAI_API_KEY is not set in config")
	}
	
	// Create speech processor
	processor := src.NewSpeechProcessor()
	
	// Kiểm tra xem client được khởi tạo chưa
	if processor.OpenAIClient == nil {
		t.Fatalf("OpenAI client not initialized - API key: %s", cfg.OpenAIAPIKey)
	}
	
	// Force TTS provider to OpenAI for this test
	origProvider := cfg.TTSProvider
	cfg.TTSProvider = "openai"
	defer func() { cfg.TTSProvider = origProvider }()
	
	// Call TextToSpeech with a simple, clear text
	text := "Testing audio generation."
	segment, err := processor.TextToSpeech(text, "test-uuid")
	
	// Check that it doesn't error
	if err != nil {
		t.Fatalf("TextToSpeech returned an error: %v", err)
	}
	
	// Check that the result is not empty
	if segment == nil || len(segment.Data) == 0 {
		t.Fatalf("TextToSpeech returned empty data")
	}
	
	// Save audio for debugging if needed
	tempFile, err := ioutil.TempFile("", "tts_test_*.mp3")
	if err == nil {
		defer os.Remove(tempFile.Name())
		defer tempFile.Close()
		
		_, err = tempFile.Write(segment.Data)
		if err == nil {
			t.Logf("Saved TTS audio to %s", tempFile.Name())
		}
	}
	
	t.Logf("TTS produced %d bytes of audio data", len(segment.Data))
}

// TestSpeechToTextOpenAI tests only the OpenAI speech-to-text functionality
func TestSpeechToTextOpenAI(t *testing.T) {
	// Check if OPENAI_API_KEY is set
	cfg := config.GetConfig()
	
	if cfg.OpenAIAPIKey == "" {
		t.Skip("Skipping test because OPENAI_API_KEY is not set in config")
	}
	
	// Generate test audio using TTS
	processor := src.NewSpeechProcessor()
	if processor.OpenAIClient == nil {
		t.Fatalf("OpenAI client not initialized - API key: %s", cfg.OpenAIAPIKey)
	}
	
	// Sử dụng một câu đơn giản nhưng rõ ràng để test
	testText := "xin chào bạn tôi là học sinh lớp 5"
	audioData, err := generateTestAudioFromText(t, processor, testText)
	if err != nil {
		t.Fatalf("Failed to generate test audio: %v", err)
	}
	
	// Force STT provider to OpenAI for this test
	origProvider := cfg.STTProvider
	cfg.STTProvider = "openai"
	defer func() { cfg.STTProvider = origProvider }()
	
	// Call SpeechToText
	result, err := processor.SpeechToText(audioData)
	
	if err != nil {
		t.Fatalf("SpeechToText returned an error: %v", err)
	}
	
	t.Logf("Expected text: %s", testText)
	t.Logf("Transcription result: %s", result)
	t.Logf("Normalized expected: %s", normalizeVietnameseText(testText))
	t.Logf("Normalized result: %s", normalizeVietnameseText(result))
	
	// Chuyển đổi cả hai về dạng không dấu, viết thường để so sánh
	// normalizedExpected := normalizeVietnameseText(testText)
	normalizedResult := normalizeVietnameseText(result)
	
	// Tìm các từ khóa chính trong câu gốc
	expectedKeywords := []string{"xin", "chao", "hoc", "sinh", "lop", "5"}
	matchedWords := 0
	
	// Kiểm tra từng từ khóa
	for _, keyword := range expectedKeywords {
		if strings.Contains(normalizedResult, keyword) {
			matchedWords++
			t.Logf("Found key word: %s", keyword)
		}
	}
	
	// Yêu cầu ít nhất nửa số từ khóa phải được nhận dạng
	if matchedWords < len(expectedKeywords)/2 {
		t.Errorf("Not enough keywords matched. Found %d out of %d", matchedWords, len(expectedKeywords))
	} else {
		t.Logf("Speech-to-text test PASSED with %d/%d key words matched!", matchedWords, len(expectedKeywords))
	}
}

// TestSimpleSpeechPipeline tests a simplified speech processing pipeline
func TestSimpleSpeechPipeline(t *testing.T) {
	// Check if OPENAI_API_KEY is set
	cfg := config.GetConfig()
	
	if cfg.OpenAIAPIKey == "" {
		t.Skip("Skipping test because OPENAI_API_KEY is not set in config")
	}
	
	// Create speech processor
	processor := src.NewSpeechProcessor()
	
	// Kiểm tra xem client được khởi tạo chưa
	if processor.OpenAIClient == nil {
		t.Fatalf("OpenAI client not initialized - API key: %s", cfg.OpenAIAPIKey)
	}
	
	// 1. Sử dụng câu test đơn giản và rõ ràng hơn, bằng tiếng Việt
	originalText := "Tôi đang kiểm tra chất lượng của bộ chuyển đổi giọng nói."
	
	// 2. Chuyển text thành speech
	origTTSProvider := cfg.TTSProvider
	cfg.TTSProvider = "openai"
	defer func() { cfg.TTSProvider = origTTSProvider }()
	
	t.Logf("Converting text to speech: %s", originalText)
	audioSegment, err := processor.TextToSpeech(originalText, "test-uuid")
	if err != nil {
		t.Fatalf("TextToSpeech returned an error: %v", err)
	}
	
	// 3. Chuyển speech thành text
	origSTTProvider := cfg.STTProvider
	cfg.STTProvider = "openai"
	defer func() { cfg.STTProvider = origSTTProvider }()
	
	t.Logf("Converting speech back to text...")
	resultText, err := processor.SpeechToText(audioSegment.Data)
	if err != nil {
		t.Fatalf("SpeechToText returned an error: %v", err)
	}
	
	t.Logf("Result from speech-to-text: %s", resultText)
	
	// Chuẩn hóa cả hai về dạng không dấu, viết thường
	normalizedOriginal := normalizeVietnameseText(originalText)
	normalizedResult := normalizeVietnameseText(resultText)
	
	t.Logf("Normalized original: %s", normalizedOriginal)
	t.Logf("Normalized result: %s", normalizedResult)
	
	// 4. Kiểm tra các từ khóa quan trọng
	keyWords := []string{"kiem", "tra", "chat", "luong", "chuyen", "doi", "giong", "noi"}
	matchedWords := 0
	
	for _, word := range keyWords {
		if strings.Contains(normalizedResult, word) {
			matchedWords++
			t.Logf("Found key word: %s", word)
		}
	}
	
	// Yêu cầu ít nhất một nửa số từ khóa phải được tìm thấy để pass test
	if matchedWords < len(keyWords)/2 {
		t.Errorf("Not enough key words matched. Found %d out of %d", matchedWords, len(keyWords))
		t.Logf("Original: %s", originalText)
		t.Logf("Result  : %s", resultText)
	} else {
		t.Logf("Speech pipeline test PASSED with %d/%d key words matched!", matchedWords, len(keyWords))
	}
}

// generateTestAudioFromText tạo audio data từ text sử dụng TTS
func generateTestAudioFromText(t *testing.T, processor *src.SpeechProcessor, text string) ([]byte, error) {
	// Lưu provider hiện tại
	cfg := config.GetConfig()
	origProvider := cfg.TTSProvider
	cfg.TTSProvider = "openai"
	defer func() { cfg.TTSProvider = origProvider }()
	
	// Generate audio data
	t.Logf("Generating test audio from text: %s", text)
	segment, err := processor.TextToSpeech(text, "test-generation")
	if err != nil {
		return nil, err
	}
	
	return segment.Data, nil
} 