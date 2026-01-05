from cuga.security.http_client import SafeClient
import os

class EmailProvider:
    def __init__(self, service='gmail'):
        self.service = service
        self.api_key = os.getenv('EMAIL_API_KEY')
        self.client = SafeClient()

    def send_email(self, to, subject, body):
        if self.service == 'gmail':
            return self._send_gmail(to, subject, body)
        elif self.service == 'outlook':
            return self._send_outlook(to, subject, body)
        else:
            raise ValueError("Unsupported email service")

    def _send_gmail(self, to, subject, body):
        # Logic to send email using Gmail API
        response = self.client.post(
            'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
            json={
                'raw': self._encode_email(to, subject, body)
            },
            headers={'Authorization': f'Bearer {self.api_key}'}
        )
        return response.json()

    def _send_outlook(self, to, subject, body):
        # Logic to send email using Outlook API
        response = self.client.post(
            'https://graph.microsoft.com/v1.0/me/sendMail',
            json={
                'message': {
                    'subject': subject,
                    'body': {
                        'contentType': 'Text',
                        'content': body
                    },
                    'toRecipients': [{'emailAddress': {'address': to}}]
                }
            },
            headers={'Authorization': f'Bearer {self.api_key}'}
        )
        return response.json()

    def _encode_email(self, to, subject, body):
        # Encode email to base64url format
        import base64
        from email.mime.text import MIMEText

        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return raw_message