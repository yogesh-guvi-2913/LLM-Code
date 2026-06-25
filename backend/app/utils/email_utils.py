
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.mime.image import MIMEImage
from app.utils.common import very_critical_log
import ssl , smtplib , os , traceback
import app.config as config , json

USERNAME = config.SMTP_USERNAME
PASSWORD = config.SMTP_PASSWORD
SMTP_SERVER = config.SMTP_SERVER
SMTP_SENDER_EMAIL = config.SMTP_SENDER_EMAIL

def sendEmail(toEmail :str, subject : str, content : str, attachements : list = [],embeddedImageInHtml : list[dict[str,str]]=[] ,textType='html' ) -> None : 
    """Raise Error If given 0 attachements or given an invalid textType , For sending embeddedImageHtml you need to send it in the following format
{
    "embedImageName" : "cid:image1" , 
    "imagePath" : "/home/ubuntu/Downloads/test.png"
}
not that in your html file image src , the src should be exactly embedImageName which is "cid:image1" all must start with cid
example calling function
sendEmailWithAttachments("sample@gmail.com", "sample subject" , content, ["README.md", "/home/gokulraj/Downloads/test.png"] , embeddedImageInHtml=[{
    "embedImageName" : "cid:image1" , 
    "imagePath" : "/home/gokulraj/Downloads/test.png"
}])
    """

    # Performing some validations 
    if textType != 'html' and textType != 'plain' : 
        print(textType)
        raise ValueError("textType can only be html or plain")
    
    for embedObject in embeddedImageInHtml : 
        embeddedImageName = embedObject['embedImageName']
        if not embeddedImageName.startswith('cid:') : 
            raise ValueError("Invalid embbeddedImageName , it must start with cid:")
        if ' ' in embeddedImageName : 
            raise ValueError("There Cannot be spaces in image names")
    
    # Creating MIMEMultipart
    message = MIMEMultipart()
    message['From'] = SMTP_SENDER_EMAIL
    message['To'] = toEmail
    message['Subject'] = subject
    # Attaching the body
    message.attach(MIMEText(content, textType))


    # Attaching attachements if any attachemnts is given
    for filePath in attachements : 
        with open(filePath, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())

            encoders.encode_base64(part)
            file_name = os.path.basename(filePath)
            part.add_header("Content-Disposition", f"attachment; filename= {file_name}")
            message.attach(part)

    # This is for embedded Image if any given , most likely It won't be used 
    for embedObject in embeddedImageInHtml : 
        embeddedImageName = embedObject['embedImageName']
        imagePath = embedObject['imagePath']
        with open(imagePath, 'rb') as img:
        # Attach the image file
            msg_img = MIMEImage(img.read(), name=os.path.basename(imagePath))
            # Define the Content-ID header to use in the HTML body
            embeddedImageName = embeddedImageName.replace('cid:' , '')
            msg_img.add_header('Content-ID', f'<{embeddedImageName}>')
            # Attach the image to the message
            message.attach(msg_img)

    # For security purpose
    context = ssl.create_default_context()
    try : 
        with smtplib.SMTP(SMTP_SERVER , 587) as smtp : 
            smtp.starttls(context=context)
            smtp.login(USERNAME, PASSWORD) 
            smtp.sendmail(SMTP_SENDER_EMAIL, toEmail , message.as_string())
    except Exception as e : 
        print(str(e)) 
        # Logging if any exception occurs 
        very_critical_log(json.dumps({"msg" : "Email failed to send" , "traceback" : str(e) }) , toEmail)
        traceback.print_exc()


# To run the the function without blocking the main loop use this code 
import asyncio
async def async_wrapper_function(sync_function, *args, **kwargs):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, sync_function, *args, **kwargs)
    return result

# This function can be used to run without blocking all other api calls implemtn accordingly 
async def sendBulkEmail(all_requied_email_fields) : 
    for val in all_requied_email_fields : 
        await async_wrapper_function(sendEmail , "requiredargs for the function")