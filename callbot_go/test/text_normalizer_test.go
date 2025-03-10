package test

import (
    "testing"
    "callbot_go/src"
)

func TestNumberToWords(t *testing.T) {
    normalizer := src.TextNormalizer{}
    tests := []struct {
        input    string
        expected string
    }{
        {"1", "một"},
        {"10", "mười"},
        {"15", "mười lăm"},
        {"20", "hai mươi"},
        {"25", "hai mươi lăm"},
        {"100", "một trăm"},
        {"101", "một trăm linh một"},
        {"1000", "một nghìn"},
    }

    for _, test := range tests {
        result := normalizer.NumberToWords(test.input)
        if result != test.expected {
            t.Errorf("NumberToWords(%s) = %s; want %s", test.input, result, test.expected)
        }
    }
}

func TestConvertDate(t *testing.T) {
    normalizer := src.TextNormalizer{}
    tests := []struct {
        input    string
        expected string
    }{
        {"25/12/2023", "ngày hai mươi lăm tháng mười hai năm hai nghìn không trăm hai mươi ba"},
        {"01/01/2024", "ngày một tháng một năm hai nghìn không trăm hai mươi bốn"},
        {"31-12-2023", "ngày ba mươi mốt tháng mười hai năm hai nghìn không trăm hai mươi ba"},
    }

    for _, test := range tests {
        result := normalizer.ConvertDate(test.input)
        if result != test.expected {
            t.Errorf("ConvertDate(%s) = %s; want %s", test.input, result, test.expected)
        }
    }
}

func TestNormalizeVietnameseText(t *testing.T) {
    normalizer := src.TextNormalizer{}
    tests := []struct {
        input    string
        expected string
    }{
        {
            "Hello!!! Tôi có 25 quả táo 🍎",
            "Hello ! Tôi có hai mươi lăm quả táo",
        },
        {
            "25/12/2023 ⭐ AI sẽ giúp chúng ta",
            "ngày hai mươi lăm tháng mười hai năm hai nghìn không trăm hai mươi ba Ây Ai sẽ giúp chúng ta",
        },
        {
            "Giá: 100000d!!!",
            "Giá : một trăm nghìn d !",
        },
        {
            "100000d",
            "một trăm nghìn d",
        },
        {
            "50k",
            "năm mươi k",
        },
    }

    for _, test := range tests {
        result := normalizer.NormalizeVietnameseText(test.input)
        if result != test.expected {
            t.Errorf("\nInput: %s\nGot:  %s\nWant: %s", test.input, result, test.expected)
        }
    }
}

func TestCheckEndConversation(t *testing.T) {
    normalizer := src.TextNormalizer{}
    tests := []struct {
        input          string
        expectedText   string
        expectedIsEnd  bool
    }{
        {"Tạm biệt ##END##", "Tạm biệt", true},
        {"Hẹn gặp lại", "Hẹn gặp lại", false},
        {"##END##", "", true},
    }

    for _, test := range tests {
        gotText, gotIsEnd := normalizer.CheckEndConversation(test.input)
        if gotText != test.expectedText || gotIsEnd != test.expectedIsEnd {
            t.Errorf("CheckEndConversation(%s) = (%s, %v); want (%s, %v)",
                test.input, gotText, gotIsEnd, test.expectedText, test.expectedIsEnd)
        }
    }
} 