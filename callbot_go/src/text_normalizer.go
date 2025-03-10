package src

import (
	"fmt"
	"regexp"
	"strings"
	"time"
	// "unicode"
)

type TextNormalizer struct {}

var digits = map[rune]string{
	'0': "không", '1' : "một", '2' : "hai", '3' : "ba", '4' : "bốn",
	'5': "năm", '6' : "sáu", '7' : "bảy", '8' : "tám", '9' : "chín",
}

var tens = map[rune]string{
	'0': "", '1' : "mười", '2' : "hai mươi", '3' : "ba mươi",
	'4': "bốn mươi", '5' : "năm mươi", '6' : "sáu mươi", '7' : "bảy mươi",
	'8': "tám mươi", '9' : "chín mươi",
}

func (t TextNormalizer) NumberToWords(number string) string {
	if len(number) == 1 {
		return digits[rune(number[0])]
	} else if len(number) == 2 {
		if number[0] == '1' {
			if number[1] == '0' {
				return "mười"
			} else if number[1] == '5' {
				return "mười lăm"
			}
			return "mười " + digits[rune(number[1])]
		}
		if number[1] == '0' {
			return tens[rune(number[0])]
		}
		if number[1] == '5' {
			return tens[rune(number[0])] + " lăm"
		}
		if number[1] == '1' {
			return tens[rune(number[0])] + " mốt"
		}
		return tens[rune(number[0])] + " " + digits[rune(number[1])]
	}

	// Xử lý số từ 3 chữ số trở lên
	switch len(number) {
	case 3: // Hàng trăm
		if number[1:] == "00" {
			return digits[rune(number[0])] + " trăm"
		}
		if number[1] == '0' {
			return digits[rune(number[0])] + " trăm linh " + digits[rune(number[2])]
		}
		return digits[rune(number[0])] + " trăm " + t.NumberToWords(number[1:])
	
	case 4: // Hàng nghìn
		if number[1:] == "000" {
			return digits[rune(number[0])] + " nghìn"
		}
		if number[1] == '0' {
			if number[2:] == "00" {
				return digits[rune(number[0])] + " nghìn"
			}
			return digits[rune(number[0])] + " nghìn không trăm " + t.NumberToWords(number[2:])
		}
		return digits[rune(number[0])] + " nghìn " + t.NumberToWords(number[1:])
	
	case 5, 6: // Hàng chục/trăm nghìn
		prefix := t.NumberToWords(number[:len(number)-3])
		if number[len(number)-3:] == "000" {
			return prefix + " nghìn"
		}
		suffix := t.NumberToWords(number[len(number)-3:])
		return prefix + " nghìn " + suffix
	
	case 7, 8, 9: // Hàng triệu
		millionPos := len(number) - 6
		prefix := t.NumberToWords(number[:millionPos])
		if number[millionPos:] == "000000" {
			return prefix + " triệu"
		}
		suffix := t.NumberToWords(number[millionPos:])
		return prefix + " triệu " + suffix
	
	case 10, 11, 12: // Hàng tỷ
		billionPos := len(number) - 9
		prefix := t.NumberToWords(number[:billionPos])
		if number[billionPos:] == "000000000" {
			return prefix + " tỷ"
		}
		suffix := t.NumberToWords(number[billionPos:])
		return prefix + " tỷ " + suffix
	}
	
	return number
}

func (t TextNormalizer) ConvertDate(match string) string {
	formats := []string{"02/01/2006","02-01-2006"}
	for _, format := range formats {
		if date, err := time.Parse(format, match); err == nil {
			return fmt.Sprintf("ngày %s tháng %s năm %s",
				t.NumberToWords(fmt.Sprint(date.Day())),
				t.NumberToWords(fmt.Sprint(int(date.Month()))),
				t.NumberToWords(fmt.Sprint(date.Year())))
		}
	}
	return match
}

func (t TextNormalizer) normalizeNumbers(text string) string {
	// Xử lý ngày tháng trước
	dateRegex := regexp.MustCompile(`\b\d{2}[-/]\d{2}[-/]\d{4}\b`)
	text = dateRegex.ReplaceAllStringFunc(text, t.ConvertDate)

	// Xử lý số có dấu chấm phân cách hàng nghìn và đơn vị đi kèm
	thousandRegex := regexp.MustCompile(`\b\d+(?:[.,]\d+)*[đdkKmM]?\b`)
	text = thousandRegex.ReplaceAllStringFunc(text, func(match string) string {
		// Tách số và đơn vị
		numStr := ""
		unit := ""
		
		// Tìm vị trí cuối cùng của số
		for i, c := range match {
			if c >= '0' && c <= '9' {
				numStr = match[:i+1]
			} else {
				unit = match[i:]
				break
			}
		}
		
		if numStr == "" {
			numStr = match
		}
		
		// Loại bỏ tất cả dấu chấm và phẩy
		num := strings.Map(func(r rune) rune {
			if r == '.' || r == ',' {
				return -1 // bỏ ký tự này
			}
			return r
		}, numStr)
		
		words := t.NumberToWords(num)
		
		// Nối với đơn vị nếu có
		if unit != "" {
			return words + " " + unit
		}
		return words
	})

	// Xử lý các số riêng lẻ còn lại
	numberRegex := regexp.MustCompile(`\b\d+\b`)
	text = numberRegex.ReplaceAllStringFunc(text, func(match string) string {
		num := strings.TrimLeft(match, "0")
		if num == "" {
			num = "0"
		}
		return t.NumberToWords(num)
	})
	return text
}

func (t TextNormalizer) normalizePunctuation(text string) string {
	// Thêm khoảng trắng trước dấu câu
	// Thay thế nhiều dấu chấm
	text = regexp.MustCompile(`\.+`).ReplaceAllString(text, ".")
	// Thay thế nhiều dấu chấm than
	text = regexp.MustCompile(`!+`).ReplaceAllString(text, "!")
	// Thay thế nhiều dấu hỏi
	text = regexp.MustCompile(`\?+`).ReplaceAllString(text, "?")
	
	punctRegex := regexp.MustCompile(`([.,!?:])`)
	text = punctRegex.ReplaceAllString(text, " $1")

	// Xóa khoảng trắng thừa trước dấu câu
	multiSpaceRegex := regexp.MustCompile(`\s+([.,!?:])`)
	text = multiSpaceRegex.ReplaceAllString(text, " $1")


	return strings.TrimSpace(text)
}

func (t TextNormalizer) removeEmojis(text string) string {
	// Regex đơn giản để loại bỏ emoji và một số ký tự đặc biệt
	emojiRegex := regexp.MustCompile(`[\x{1F600}-\x{1F64F}]|[\x{1F300}-\x{1F5FF}]|[\x{1F680}-\x{1F6FF}]|[\x{1F1E0}-\x{1F1FF}]|[\x{2702}-\x{27B0}]|[\x{24C2}-\x{1F251}]`)
	return emojiRegex.ReplaceAllString(text, "")
}

func (t TextNormalizer) NormalizeVietnameseText(text string) string {
	// Loại bỏ emoji và ký tự đặc biệt
	text = t.removeEmojis(text)

	// Xử lý dấu câu
	text = t.normalizePunctuation(text)
	
	// Xử lý số và ngày tháng
	text = t.normalizeNumbers(text)


	// Các thay thế đặc biệt
	replacements := map[string]string{
		`"`: "",
		"'": "",
		"AI": "Ây Ai",
		"A.I": "Ây Ai",
		"…": "...",
		"️": "",     // Variation selector
		"⭐": "",    // Ngôi sao
		"★": "",     // Ngôi sao khác dạng
		"☆": "",     // Ngôi sao rỗng
		"♥": "",     // Trái tim
		"❤": "",     // Trái tim khác dạng
	}

	for old, new := range replacements {
		text = strings.ReplaceAll(text, old, new)
	}

	// Loại bỏ khoảng trắng thừa
	text = strings.Join(strings.Fields(text), " ")
	return strings.TrimSpace(text)
}

func (t TextNormalizer) CheckEndConversation(text string) (string, bool) {
	if strings.Contains(text, "##END##") {
		return strings.TrimSpace(strings.ReplaceAll(text, "##END##", "")), true
	}
	return text, false
}