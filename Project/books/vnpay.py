import hashlib
import hmac
import urllib.parse
from datetime import datetime

class VNPay:
    def __init__(self, tmn_code, hash_key, return_url, api_url):
        self.tmn_code = tmn_code
        self.hash_key = hash_key
        self.return_url = return_url
        self.api_url = api_url

    def get_payment_url(self, order_id, amount, order_desc, ipaddr):
        vnp_params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': self.tmn_code,
            'vnp_Amount': int(amount * 100),
            'vnp_CreateDate': datetime.now().strftime('%Y%m%d%H%M%S'),
            'vnp_CurrCode': 'VND',
            'vnp_IpAddr': ipaddr,
            'vnp_Locale': 'vn',
            'vnp_OrderInfo': order_desc,
            'vnp_OrderType': 'topup',
            'vnp_ReturnUrl': self.return_url,
            'vnp_TxnRef': str(order_id),
        }

        # Sắp xếp params theo alphabet
        vnp_params = dict(sorted(vnp_params.items()))
        
        # Tạo chuỗi query
        query_string = urllib.parse.urlencode(vnp_params)
        
        # Tạo mã hash checksum
        hash_data = query_string
        hmac_algo = hmac.new(self.hash_key.encode('utf-8'), hash_data.encode('utf-8'), hashlib.sha512)
        vnp_secure_hash = hmac_algo.hexdigest()
        
        payment_url = f"{self.api_url}?{query_string}&vnp_SecureHash={vnp_secure_hash}"
        return payment_url

    def validate_response(self, query_params):
        vnp_secure_hash = query_params.get('vnp_SecureHash')
        # Loại bỏ vnp_SecureHash và vnp_SecureHashType khỏi params để tính toán lại hash
        params = {k: v for k, v in query_params.items() if k not in ['vnp_SecureHash', 'vnp_SecureHashType']}
        params = dict(sorted(params.items()))
        
        query_string = urllib.parse.urlencode(params)
        hmac_algo = hmac.new(self.hash_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha512)
        expected_hash = hmac_algo.hexdigest()
        
        return vnp_secure_hash == expected_hash
