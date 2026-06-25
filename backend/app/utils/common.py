from icecream.icecream import ic
import json, datetime, time, hashlib, random, base64, io, boto3
from botocore.config import Config
from app.config import PASSWORD_SALT, TOKEN_SALT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET
from app.postgresql.sync.postgres import PostgreSQL
import uuid, logging
from botocore.config import Config
import uuid, copy
import re
from urllib.parse import urlparse
import requests

logger = logging.getLogger(__name__)

def my_print(*anything) : 
    print(*anything)

def my_log(message , message_id , log_level="INFO") :
    f = open("logs.log" , "a")
    today_date = datetime.date.today()
    # Get current time
    current_time = datetime.datetime.now().time()
    text = ''
    if log_level == "INFO" : 
        text = f"{today_date} {current_time} INFO " + json.dumps({"message" : message , "message_id" : message_id})
    elif log_level == "DEBUG" : 
        text = f"{today_date} {current_time} DEBUG " + json.dumps({"message" : message , "message_id" : message_id})
    elif log_level == "WARNING" : 
        text = f"{today_date} {current_time} WARNING " + json.dumps({"message" : message , "message_id" : message_id})
    elif log_level == "ERROR" :
        text = f"{today_date} {current_time} ERROR " + json.dumps({"message" : message , "message_id" : message_id})
    elif log_level == "CRITICAL" :
        text = f"{today_date} {current_time} CRITICAL " + json.dumps({"message" : message , "message_id" : message_id})

    f.write(text + '\n')
    f.close()

def very_critical_log(message , message_id) : 
    with open('critical_error.log' , 'a') as f : 
        today_date = datetime.date.today()
        current_time = datetime.datetime.now().time()
        text = f"{today_date} {current_time} CRITICAL " + json.dumps({"message" : message , "message_id" : message_id}) + '\n'
        f.write(text)


def successResponse(data: str | list | dict = {}, status: str = 'success'):
    return {
        'status': status,
        'data': data
    }

def failureResponse(message: str = 'ACCESS_DENIED', status: str = 'error', data: str | list | dict | bool = False, errorCode: str = 'E401'):
    # errorCode should be start from e1 to e99
    resposne = {
        'status': status,
        'message': message,
        'errorCode': errorCode
    }

    # Add data if exists
    if data:
        resposne['data'] = data
    
    return resposne

def getCurrentTime() : 
    return round(time.time() * 1000)

def getPasswordHash(password):
    # Hash the password with the salt using SHA-256
    salt = hashlib.sha256(PASSWORD_SALT.encode()).digest()
    hashedPassword = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    # Return the hashed password
    return hashedPassword.hex()

def generateUserHash(email, createAt):
    inputString = email + str(createAt)
    hash = hashlib.pbkdf2_hmac('sha256', inputString.encode('utf-8'), b'', 1)
    return hash.hex()

def generateUserHashForGuviUser(email):
    userHash = False
    try:
        validatedEmail = email.strip().lower()
        encodedEmail = validatedEmail.encode("utf-8")
        userHash = hashlib.sha512(encodedEmail).hexdigest()
    except Exception as e:
        logger.error(f"Error generating user hash for email {email}: {str(e)}")
    return userHash

def generateToken(hash):
    # Create salt
    salt = TOKEN_SALT + str(time.time())
    
    # Create timestamp
    random_value = str(random.randint(0, 1000000)) + str(time.time())
    timestamp = hashlib.sha512(random_value.encode()).hexdigest()[:40]
    
    # Hash the token ID using SHA-512
    tokenid = hash + salt + timestamp
    hash_token = hashlib.sha512(tokenid.encode()).hexdigest()
    
    return hash_token

def isJson(string):
    try:
        json.loads(string)
    except Exception as e:
        return False
    return True

def safeInt(string):
    parsedNumber = 0
    try:
        parsedNumber = int(string)
    except Exception as e:
        return 0
    return parsedNumber

def validateUNIXTime(givenTime: int):
    response = False
    try:
        isTimeValid =  time.localtime(givenTime)
        response = True
    except Exception as e:
        logger.error(f"Invalid UNIX time: {givenTime}. Error: {str(e)}")
    return response

def commonLog(fromCollection, logType, logKey, data, createdBy=False):
    logId = str(uuid.uuid4())
    currentTime = getCurrentTime()
    postgresDb = PostgreSQL()
    mongoDb.selectDB()
    mongoDb.selectCollection('log')
    mongoDb.insertOne({
        'logId': logId,
        'from': fromCollection,
        'type': logType,
        'logKey': logKey,
        'data': data,
        'createdAt': currentTime,
        'createdBy': createdBy
    })

def createHackathonLog(draftId, stepNo, createdBy, data = False):
    logId = str(uuid.uuid4())
    currentTime = getCurrentTime()
    postgresDb = PostgreSQL()
    mongoDb.selectDB()
    mongoDb.selectCollection('drafts-log')
    insertData = {
        'logId': logId,
        'draftId': draftId,
        'stepNo': stepNo,
        'createdAt': currentTime,
        'createdBy': createdBy
    }
    if data:
        insertData['data'] = data
    mongoDb.insertOne(insertData)

def blobToBytes(file):
    try:
        bytes = base64.b64decode(file)
        file = io.BytesIO(bytes)
        return file
    except Exception as e:
        logger.error(f"Error converting blob to bytes: {str(e)}")
        return False
    
def uploadInS3(file, objectKey, returnParams=True):
    try:
        # Upload in s3
        s3 = boto3.client('s3', aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY)
        s3.upload_fileobj(file, S3_BUCKET, objectKey)
        url = s3.generate_presigned_url('get_object', Params={'Bucket': S3_BUCKET, 'Key': objectKey},  ExpiresIn=None)
        if not returnParams:
            url = f"https://{S3_BUCKET}.s3.ap-south-1.amazonaws.com/{objectKey}"
        return url
    except Exception as e:
        logger.error(f"Error uploading file to S3: {str(e)}")
        return False
    
def is_valid_s3_url(url: str, verify_access: bool = False) -> dict:
    if not url or not isinstance(url, str):
        return {'valid': False, 'message': 'URL is required'}

    # Define S3 URL patterns
    s3_patterns = [
        # Virtual-hosted style: https://bucket-name.s3.region.amazonaws.com/key
        r'^https?://([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])\.s3[.-]([a-z0-9-]+)\.amazonaws\.com(/.*)?$',
        # Path-style: https://s3.region.amazonaws.com/bucket-name/key
        r'^https?://s3[.-]([a-z0-9-]+)\.amazonaws\.com/([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])(/.*)?$',
        # S3 website hosting: http://bucket-name.s3-website-region.amazonaws.com
        r'^https?://([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])\.s3-website[.-]([a-z0-9-]+)\.amazonaws\.com(/.*)?$',
        # CloudFront or custom domains (basic check for https with valid domain)
        r'^https?://([a-z0-9][a-z0-9.-]{1,61}[a-z0-9])(\.cloudfront\.net|\.s3-website[.-][a-z0-9-]+\.amazonaws\.com)(/.*)?$',
    ]

    # Parse URL to check basic structure
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {'valid': False, 'message': 'Invalid URL format'}
        if parsed.scheme not in ['http', 'https']:
            return {'valid': False, 'message': 'URL must use http or https protocol'}
    except Exception as e:
        return {'valid': False, 'message': f'Invalid URL: {str(e)}'}

    # Check if URL matches any S3 pattern
    is_s3_pattern = any(re.match(pattern, url) for pattern in s3_patterns)

    if not is_s3_pattern:
        # Additional check for any amazonaws.com domain (more lenient)
        if 'amazonaws.com' not in parsed.netloc and 'cloudfront.net' not in parsed.netloc:
            return {'valid': False, 'message': 'URL must be a valid S3 or CloudFront URL'}

    # Optionally verify the URL is accessible
    if verify_access:
        try:
            response = requests.head(url, timeout=5, allow_redirects=True)
            if response.status_code not in [200, 301, 302, 304]:
                return {'valid': False, 'message': f'URL is not accessible (status: {response.status_code})'}
        except requests.RequestException as e:
            return {'valid': False, 'message': f'Failed to verify URL accessibility: {str(e)}'}

    return {'valid': True, 'message': 'Valid S3 URL'}


def generateS3PresignedUrl(objectKey, contentType=None, expiresIn=3600):
    """
    Generate a presigned URL for S3 upload
    Args:
        objectKey: The S3 object key (path where file will be stored)
        contentType: Optional content type of the file (note: not included in signature to avoid header mismatch issues)
        expiresIn: URL expiration time in seconds (default: 3600 = 1 hour)
    Returns:
        dict with presignedUrl and objectKey, or False on error
    """
    try:
        s3 = boto3.client(
            's3',
            region_name='ap-south-1',  # ⚠️ change to your bucket region
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            config=Config(signature_version='s3v4')
        )

        # s3 = boto3.client('s3', aws_access_key_id=S3_ACCESS_KEY, aws_secret_access_key=S3_SECRET_KEY)

        params = {
            'Bucket': S3_BUCKET,
            'Key': objectKey
        }

        # Note: We're NOT including ContentType in params to avoid signature mismatch issues
        # The client can still send Content-Type header but it won't be validated by S3

        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params=params,
            ExpiresIn=expiresIn
        )

        # Also generate the final URL that will be used to access the file
        final_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{objectKey}"

        return {
            'presignedUrl': presigned_url,
            'objectKey': objectKey,
            'finalUrl': final_url,
            'bucket': S3_BUCKET
        }
    except Exception as e:
        logger.error(f"Error generating S3 presigned URL: {str(e)}")
        return False

def base64_encode(input_string):
    # Convert the input string to bytes
    byte_data = input_string.encode('utf-8')
    
    # Encode the bytes in base64
    encoded_data = base64.b64encode(byte_data)
    
    # Convert the encoded bytes back to a string
    encoded_string = encoded_data.decode('utf-8')
    
    return encoded_string
    
def base64_decode(encoded_string):
    # Convert the encoded string to bytes
    byte_data = encoded_string.encode('utf-8')
    
    # Decode the base64 bytes
    decoded_data = base64.b64decode(byte_data)
    
    # Convert the decoded bytes back to a string
    decoded_string = decoded_data.decode('utf-8')
    
    return decoded_string

def generateUserNameFromConfig(hackathonId, userNameConfig, registrationData):
    # Minimum one registration field or dynamic field is required
    if not (userNameConfig and (('registrationFields' in userNameConfig and len(userNameConfig['registrationFields']) > 0) or ('dynamicFields' in userNameConfig and len(userNameConfig['dynamicFields']) > 0))):
        return False

    userNameGenerationVariables = {}
        
    if 'registrationFields' in userNameConfig:
        # Ensure all fields required for username creation are present in user uploaded data
        for field in userNameConfig['registrationFields']:
            if field not in registrationData:
                return False
            userNameGenerationVariables[field] = registrationData[field]
    
    if 'dynamicFields' in userNameConfig:
        for field in userNameConfig['dynamicFields']:
            # CAUTION!! The registration fields used to generate username should not be updated at any cost, because it may affect the sequence
            if field == 'SEQ_4_DIGIT':
                # Use findOneAndUpdate to atomically increment a counter
                postgresDb = PostgreSQL()
                mongoDb.selectDB()
                mongoDb.selectCollection('uniqueCounters')

                # Form a object with hackathonId and registrationFields
                counterQuery = {'hackathonId': hackathonId, 'type': 'usernameSeq'}
                if 'registrationFields' in userNameConfig:
                    for eachField in userNameConfig['registrationFields']:
                        counterQuery[eachField] = registrationData[eachField]

                updateData = {'$inc': {'seq': 1}}
                
                countUpdated = mongoDb.findOneAndUpdate(
                    counterQuery,
                    updateData,
                    upsert=True
                )

                userNameGenerationVariables[field] = str(countUpdated['seq']).zfill(4)
            else: 
                # If the dynamic field is not supported, return False
                return False
    
    # Check for base patern
    newUserName = ''
    if 'basePattern' in userNameConfig:
        basePattern = userNameConfig['basePattern']
        for key, value in userNameGenerationVariables.items():
            basePattern = basePattern.replace(f"{{{{{key}}}}}", value)
        newUserName = basePattern

    if not newUserName:
        return False
    
    return newUserName
    
def generateEmailFromUserName(userName, baseEmail):
    if not (userName and baseEmail):
        return False
    
    generatedEmail = baseEmail.replace("{{USERNAME}}", userName)

    # Ensure it is generated unique
    postgresDb = PostgreSQL()
    mongoDb.selectDB()
    mongoDb.selectCollection('user')
    findQuery = {
        'email': generatedEmail
    }
    if mongoDb.count(findQuery) > 0:
        return False
    
    return generatedEmail

def generatePasswordFromConfig(passwordConfig, registrationData):
    # Minimum one registration field or dynamic field is required or staic password is also allowed
    if not (passwordConfig and (('registrationFields' in passwordConfig and len(passwordConfig['registrationFields']) > 0) or ('dynamicFields' in passwordConfig and len(passwordConfig['dynamicFields']) > 0) or ('basePattern' in passwordConfig and len(passwordConfig['basePattern']) > 0))):
        return False
    
    passwordGenerationVariables = {}
    if 'registrationFields' in passwordConfig:
        registrationFields = passwordConfig['registrationFields']
        # Ensure all fields required for password creation are present in user uploaded data
        for field in registrationFields:
            if field not in registrationData:
                return False
            passwordGenerationVariables[field] = registrationData[field]

    if 'dynamicFields' in passwordConfig:
        for field in passwordConfig['dynamicFields']:
            # Yet to implemented
            return False
        
    # Apply transformations if defined
    transformations = passwordConfig.get('transformations', {})
    for field, transformation in transformations.items():
        if field not in passwordGenerationVariables:
            continue
        
        value = passwordGenerationVariables[field]
        transformType = transformation.get('type') if isinstance(transformation, dict) else transformation
        stripChars = transformation.get('stripChars', []) if isinstance(transformation, dict) else []
        minLength = transformation.get('minLength', 1) if isinstance(transformation, dict) else 1
        padChar = transformation.get('padChar', '_') if isinstance(transformation, dict) else '_'
        padPosition = transformation.get('padPosition', 'RIGHT') if isinstance(transformation, dict) else 'RIGHT'

        # Strip unwanted characters (e.g., dots and spaces)
        for char in stripChars:
            value = value.replace(char, '')

        # Apply transformation type
        if transformType == 'FIRST_2_CHARS_UPPERCASE':
            value = value[:2].upper()
        elif transformType == 'FIRST_4_CHARS_UPPERCASE':
            value = value[:4].upper()
        elif transformType == 'FIRST_CHAR':
            value = value[:1].upper()
        
        # Pad if value is shorter than minLength
        if len(value) < minLength:
            if padPosition == 'RIGHT':
                value = value.ljust(minLength, padChar)
            elif padPosition == 'LEFT':
                value = value.rjust(minLength, padChar)

        passwordGenerationVariables[field] = value
    
    # Build password from base pattern
    newPassword = ''
    if 'basePattern' in passwordConfig:
        basePattern = passwordConfig['basePattern']
        for key, value in passwordGenerationVariables.items():
            if key == 'dob':
                value = value.replace('/', '')
            basePattern = basePattern.replace(f"{{{{{key}}}}}", value)
        newPassword = basePattern

    if not newPassword:
        return False
    
    return newPassword

def getUniqueId(prefix: str = ''):
    if prefix:
        return f"{prefix}-{str(uuid.uuid4())}"
    return str(uuid.uuid4())