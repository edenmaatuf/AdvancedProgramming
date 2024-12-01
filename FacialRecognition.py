import requests
import base64
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
import boto3
import os
from deepface import DeepFace
from scipy.spatial.distance import cosine
import numpy as np
import cv2
from picamera2 import Picamera2
import time

# Configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_EMAIL = 'edenandavishag@gmail.com'
SENDER_PASSWORD = 'yupaimyhuvwghxue'
RECIPIENT_EMAIL = 'avishags65@gmail.com'
S3_BUCKET = "avishageden"
IMAGES_FOLDER = "ServerImages"
CAPTURED_IMAGE = 'CapturedImage.JPG'

# Email Sending Function
def send_notification_email(subject_line, message_content, file_attachment=None, embedded_image=None):
    try:
        email = MIMEMultipart()
        email['From'] = SENDER_EMAIL
        email['To'] = RECIPIENT_EMAIL
        email['Subject'] = subject_line

        # Attach message content
        email.attach(MIMEText(message_content, 'plain'))

        # Add a file as an attachment
        if file_attachment:
            with open(file_attachment, 'rb') as attachment_file:
                attached_file = MIMEBase('application', 'octet-stream')
                attached_file.set_payload(attachment_file.read())
            encoders.encode_base64(attached_file)
            attached_file.add_header(
                'Content-Disposition',
                f'attachment; filename="{os.path.basename(file_attachment)}"'
            )
            email.attach(attached_file)

        # Embed an image within the email
        if embedded_image:
            with open(embedded_image, 'rb') as image_file:
                inline_image = MIMEImage(image_file.read())
                inline_image.add_header('Content-ID', '<image>')
                inline_image.add_header(
                    'Content-Disposition',
                    f'inline; filename="{os.path.basename(embedded_image)}"'
                )
                email.attach(inline_image)

        # Establish connection and send the email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, email.as_string())

        print("Email sent successfully.")

    except Exception as e:
        print(f"Email failed to send: {e}")

# S3 Download
def download_images_from_s3():
    if not os.path.exists(IMAGES_FOLDER):
        os.makedirs(IMAGES_FOLDER)
    else:
        for existing_file in os.listdir(IMAGES_FOLDER):
            os.remove(os.path.join(IMAGES_FOLDER, existing_file))

    s3_client = boto3.client('s3')

    try:
        objects = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        if 'Contents' not in objects:
            print("No images found in the S3 bucket.")
            return

        for item in objects['Contents']:
            if item['Key'].lower().endswith('.jpg'):
                local_path = os.path.join(IMAGES_FOLDER, os.path.basename(item['Key']))
                s3_client.download_file(S3_BUCKET, item['Key'], local_path)

        print("Images downloaded successfully.")

    except Exception as e:
        print(f"Error during image download: {e}")

# Face Matching
def validate_face_match(target_image, test_image, similarity_threshold=0.6):
    try:
        target_embedding = DeepFace.represent(img_path=target_image, model_name='Facenet', enforce_detection=False)[0]['embedding']
        test_embedding = DeepFace.represent(img_path=test_image, model_name='Facenet', enforce_detection=False)[0]['embedding']
        distance = cosine(np.array(target_embedding), np.array(test_embedding))
        return distance < similarity_threshold
    except Exception as e:
        print(f"Face matching error: {e}")
        return False

# Face Detection in Frame
def detect_face_in_frame(image_frame):
    gray_image = cv2.cvtColor(image_frame, cv2.COLOR_BGR2GRAY)
    face_classifier = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_classifier.detectMultiScale(gray_image, 1.1, 4)
    return len(faces) > 0

# Real-Time Processing
def process_camera_feed():
    os.environ["LIBCAMERA_LOG_LEVELS"] = "*:ERROR"
    download_images_from_s3()
    camera = Picamera2()
    camera.configure(camera.create_video_configuration())
    camera.start()

    try:
        while True:
            camera.start_and_capture_file(CAPTURED_IMAGE)
            frame = cv2.imread(CAPTURED_IMAGE)

            if detect_face_in_frame(frame):
                print("Face detected in frame.")
                for stored_image in os.listdir(IMAGES_FOLDER):
                    if stored_image.endswith('.jpg'):
                        if validate_face_match(CAPTURED_IMAGE, os.path.join(IMAGES_FOLDER, stored_image)):
                            print("Match found. Access granted.")
                            return
                print("Unauthorized access attempt.")
                send_notification_email(
                    subject_line="Unauthorized Access Detected",
                    message_content="An unauthorized attempt was detected. Image is attached.",
                    embedded_image=CAPTURED_IMAGE
                )
            time.sleep(2)

    except KeyboardInterrupt:
        camera.close()

if __name__ == "__main__":
    process_camera_feed()
