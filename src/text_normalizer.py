from underthesea import text_normalize as TTSnorm
import re
from datetime import datetime

class TextNormalizer:
    # Định nghĩa các từ điển chuyển đổi số
    DIGITS = {
        '0': 'không', '1': 'một', '2': 'hai', '3': 'ba', '4': 'bốn',
        '5': 'năm', '6': 'sáu', '7': 'bảy', '8': 'tám', '9': 'chín'
    }
    
    TENS = {
        '1': 'mười',
        '2': 'hai mươi',
        '3': 'ba mươi',
        '4': 'bốn mươi',
        '5': 'năm mươi',
        '6': 'sáu mươi',
        '7': 'bảy mươi',
        '8': 'tám mươi',
        '9': 'chín mươi'
    }

    @staticmethod
    def number_to_words(number):
        """Convert a number to Vietnamese words"""
        if not isinstance(number, str):
            number = str(number)
            
        # Xử lý số có 1 chữ số
        if len(number) == 1:
            return TextNormalizer.DIGITS[number]
            
        # Xử lý số có 2 chữ số
        if len(number) == 2:
            if number[0] == '1':
                if number[1] == '0':
                    return 'mười'
                if number[1] == '5':
                    return 'mười lăm'
                return f"mười {TextNormalizer.DIGITS[number[1]]}"
            
            if number[1] == '0':
                return TextNormalizer.TENS[number[0]]
            if number[1] == '5':
                return f"{TextNormalizer.TENS[number[0]]} lăm"
            return f"{TextNormalizer.TENS[number[0]]} {TextNormalizer.DIGITS[number[1]]}"
            
        # Với số lớn hơn, có thể thêm xử lý tùy nhu cầu
        return number

    @staticmethod
    def convert_date(match):
        """Convert date string to words"""
        date_str = match.group(0)
        try:
            # Hỗ trợ cả định dạng / và -
            if '/' in date_str:
                date = datetime.strptime(date_str, '%d/%m/%Y')
            else:
                date = datetime.strptime(date_str, '%d-%m-%Y')
                
            day = TextNormalizer.number_to_words(date.day)
            month = TextNormalizer.number_to_words(date.month)
            year = TextNormalizer.number_to_words(date.year)
            
            return f"ngày {day} tháng {month} năm {year}"
        except:
            return date_str

    @staticmethod
    def normalize_numbers(text):
        """Convert number strings like "02" to words"""
        # Xử lý ngày tháng trước
        text = re.sub(r'\b\d{2}[-/]\d{2}[-/]\d{4}\b', TextNormalizer.convert_date, text)
        
        # Sau đó xử lý các số riêng lẻ
        def convert_number(match):
            num = match.group(0)
            # Bỏ các số 0 ở đầu
            num = str(int(num))
            return TextNormalizer.number_to_words(num)
            
        # Tìm và thay thế các số
        text = re.sub(r'\b\d+\b', convert_number, text)
        return text
    
    @staticmethod
    def normalize_punctuation(text):
        """Add spaces before punctuation and normalize multiple punctuation"""
        text = re.sub(r'([.,!?])', r' \1', text)  # Add space before punctuation
        text = re.sub(r'\s+([.,!?])', r' \1', text)  # Remove extra spaces
        text = re.sub(r'\.+', '.', text)  # Replace multiple dots
        text = re.sub(r'!+', '!', text)  # Replace multiple exclamation marks
        text = re.sub(r'\?+', '?', text)  # Replace multiple question marks
        return text.strip()

    @staticmethod
    def remove_emojis(text):
        """Remove emojis and special characters from text"""
        # Pattern để match emoji và một số ký tự đặc biệt
        emoji_pattern = re.compile("["
            u"\U0001F600-\U0001F64F"  # emoticons
            u"\U0001F300-\U0001F5FF"  # symbols & pictographs
            u"\U0001F680-\U0001F6FF"  # transport & map symbols
            u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
            u"\U00002702-\U000027B0"
            u"\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE)
        return emoji_pattern.sub('', text)

    @staticmethod
    def normalize_vietnamese_text(text):
        """Normalize Vietnamese text for TTS"""
        # Loại bỏ emoji và ký tự đặc biệt
        text = TextNormalizer.remove_emojis(text)
        
        # Chuẩn hóa cơ bản với underthesea
        text = TTSnorm(text)
        
        # Xử lý số và ngày tháng
        text = TextNormalizer.normalize_numbers(text)
        
        # Xử lý dấu câu
        text = TextNormalizer.normalize_punctuation(text)
        
        # Các thay thế đặc biệt
        replacements = {
            '"': '',
            "'": '',
            "AI": "Ây Ai",
            "A.I": "Ây Ai",
            "…": "...",  # Thêm xử lý cho dấu ba chấm
            "️": "",     # Loại bỏ variation selector
            "⭐": "",    # Loại bỏ ngôi sao
            "★": "",     # Loại bỏ ngôi sao khác dạng
            "☆": "",     # Loại bỏ ngôi sao rỗng
            "♥": "",     # Loại bỏ trái tim
            "❤": "",     # Loại bỏ trái tim khác dạng
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
            
        # Loại bỏ khoảng trắng thừa
        text = ' '.join(text.split())
        return text.strip()

    @staticmethod
    def check_end_conversation(text):
        """Check if text contains end conversation marker"""
        if "##END##" in text:
            # Remove the marker and return cleaned text and True flag
            return text.replace("##END##", "").strip(), True
        return text, False 