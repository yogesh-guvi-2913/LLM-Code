import json, logging
import traceback
from urllib.parse import parse_qs
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.common import failureResponse, getCurrentTime, safeInt
from app.redis.sync.rediscache import RedisCache
from app.postgresql.sync.postgres import PostgreSQL
from app.utils.endpoints import authorization, admin, participants, external, project, allowHigherRateLimitter
from app.utils.constants import ALLOWED_CONTENT_TYPES, ALLOWED_REQUEST_METHODS, ALLOWED_PATHS_FOR_DOCS, ALLOWED_PATHS_FOR_METRICS, ALLOWED_PATHS_FOR_HEALTH
from app.config import ENVIRONMENT
from app.hooks.authorize import getExternalAPIKeyDetails, logExternalAPIRequests
from app.hooks.participants import getHackathonMetaData

logger = logging.getLogger(__name__)

class AuthenticationMiddleware(BaseHTTPMiddleware):

    # add allowed routes here
    allowedEndpoints = authorization + admin + participants + external + project
    # add routes which requires authToken check
    authenticatedRoutes = participants
    # add routes which each role can access
    participantPaths = participants + project
    adminPaths = admin
    externalPaths = external
    allowHigherRateLimitter = allowHigherRateLimitter

    def validateExternalApiKeys(self, request, apiKey):
        try:
            apiKeyResponse = getExternalAPIKeyDetails(apiKey)
            if not (apiKeyResponse and 'apiKey' in apiKeyResponse):
                return False

            if apiKeyResponse['apiKey'] == apiKey:
                postgresDb = PostgreSQL()
                postgresDb.selectDB()
                postgresDb.selectCollection('externalApi')
                postgresDb.updateOne({'apiKey': apiKey}, {'$inc': {'usage': 1}})
                return True
            return False
        except Exception as e:
            return False

    def authenticationCheck(self, request, requestData):
        # Check the endpoint is allowed
        if not (request.url.path in self.allowedEndpoints):
            return False
        # Check for API key in Header for external paths
        if request.url.path in self.externalPaths:
            apiKey = request.headers.get('api-key')
            if not (apiKey and len(apiKey) > 0 and self.validateExternalApiKeys(request, apiKey)):
                return False
        # Check the path is to be authenticated
        if request.url.path in self.authenticatedRoutes:
            # Check authToken is present and valid
            if 'authToken' not in requestData or not requestData['authToken'] or RedisCache().checkKeyExists(requestData['authToken']) != 1:
                return False
        return True
    
    def authorizationCheck(self, request, requestData):
        path = request.url.path

        # Add common routes with does not require auth check here
        if path in authorization:
            return True
        
        # Now there is now restriction for external paths, Add role based access here
        if request.url.path in self.externalPaths:
            return True

        # Check for authorization
        role = RedisCache().getData(requestData['authToken'], 'role') if 'authToken' in requestData and requestData['authToken'] else None
        if role == 'admin':
            return True
        elif role == 'super_admin':
            return True
        elif role == 'user' and path in self.participantPaths:
            return True
        return False
    
    def rateLimitter(self, request, requestData):
        redisCache = RedisCache()

        host  = request.client.host
        path = request.url.path
        apiKey = request.headers.get('api-key')

        # Choose either authtoken or host as user identifier or API-key for external endpoints
        userIdentifier = requestData['authToken'] if 'authToken' in requestData and requestData['authToken'] and redisCache.checkKeyExists(requestData['authToken']) else host

        # Default rate limitter configurations
        allowedMaxRequests = 500 # !@# Later after adding recaptcha for unauth endpoints, change this to 50 for safer limit
        timeRangeInSeconds = 5
        banTimeInSeconds = 60 * 60 # one hour

        # Check it is an extrenal API and check ratelimit config is present
        if request.url.path in self.externalPaths and apiKey:
            userIdentifier = apiKey
            
            # Check for Rate Limitter config for this API key
            apiKeyResponse = getExternalAPIKeyDetails(apiKey)
            if apiKeyResponse and 'apiKey' in apiKeyResponse and 'rateLimitter' in apiKeyResponse and 'maxRequestCount' in apiKeyResponse['rateLimitter'] and 'intervalInSeconds' in apiKeyResponse['rateLimitter'] and safeInt(apiKeyResponse['rateLimitter']['maxRequestCount']) and safeInt(apiKeyResponse['rateLimitter']['intervalInSeconds']):
                allowedMaxRequests = safeInt(apiKeyResponse['rateLimitter']['maxRequestCount'])
                timeRangeInSeconds = safeInt(apiKeyResponse['rateLimitter']['intervalInSeconds'])
        
        # Check it in allowHigherRateLimitter
        if request.url.path in self.allowHigherRateLimitter:
            allowedMaxRequests = 500
            timeRangeInSeconds = 5

        # Build redis keys for ratelimtter
        rateLimiterRedisKey = f'rateLimiter:{path}:{userIdentifier}:'
        rateLimiterBannedKey = f'rateLimiterBan:{path}:{userIdentifier}'

        # Check for Rate Ban list
        if redisCache.checkKeyExists(rateLimiterBannedKey):
            return False

        redisCache.incrementValue(rateLimiterRedisKey)
        if redisCache.getExpireTime(rateLimiterRedisKey) == -1:
            redisCache.expireKey(rateLimiterRedisKey, timeRangeInSeconds)
        
        requestCount = safeInt(redisCache.getValue(rateLimiterRedisKey))
        
        if requestCount and requestCount > allowedMaxRequests:
            redisCache.setValue(rateLimiterBannedKey, getCurrentTime())
            redisCache.expireKey(rateLimiterBannedKey, banTimeInSeconds)
            return False

        # Check for external API and log the request payload with host
        if request.url.path in self.externalPaths:
            logExternalAPIRequests(apiKey, host, str(request.url), requestData)
        
        return True

    def customEndpointCheck(self, request, requestData):
        # Only check for path, which has prefix 'custom'
        if '/custom/' not in request.url.path:
            return True

        hackathonId = requestData.get('hackathonId', None)
        if not hackathonId:
            return False

        hackathonData = getHackathonMetaData(hackathonId)
        if not hackathonData:
            return False
        
        if 'customEndpointId' not in hackathonData:
            return False
        
        customEndpointId = hackathonData['customEndpointId']
        extractedCustomEndpointFromPath = request.url.path.split('/custom/')[1].split('/')[0] if '/custom/' in request.url.path else None
        # Validate and allow only the specific custom endpoint
        if customEndpointId == extractedCustomEndpointFromPath:
            return True
        
        return False
    
    async def dispatch(self, rawRequest, call_next):
        try:
            request : Request = rawRequest
            requestContentType = request.headers.get('content-type', '').split(';')[0]
            # Sanitize endpoint path
            request.scope['path'] = request.scope['path'].replace('/api', '').rstrip('/')
            response = {}
            if request.method == 'GET' and request.url.path in ALLOWED_PATHS_FOR_HEALTH:
                response = await call_next(rawRequest)
            elif request.method == 'GET' and request.url.path in ALLOWED_PATHS_FOR_METRICS:
                response = await call_next(rawRequest)
            elif request.method == 'GET' and ENVIRONMENT == 'development' and request.url.path in ALLOWED_PATHS_FOR_DOCS:
                response = await call_next(rawRequest)
            elif request.method not in ALLOWED_REQUEST_METHODS:
                response = JSONResponse(failureResponse('INVALID_REQUEST_METHOD'))
            elif not (requestContentType in ALLOWED_CONTENT_TYPES):
                response = JSONResponse(failureResponse('INVALID_REQUEST_CONTENT_TYPE'))
            else:
                requesteData = {}
                if requestContentType == 'application/json':
                    requesteData = await request.json()
                else:
                    requestBody = await request.body()
                    decodeRequest = parse_qs(requestBody.decode('utf-8'))
                    extractRequest = {key: val[0] for key, val in decodeRequest.items()}
                    requesteData = json.loads(extractRequest['myData'])

                # Check for authentication and authorization for the endpoint path
                if self.authenticationCheck(request, requesteData) != True:
                    response = JSONResponse(failureResponse())
                elif self.authorizationCheck(request, requesteData) != True:
                    response = JSONResponse(failureResponse('UNAUTHORIZED_ACCESS'))
                elif self.rateLimitter(request, requesteData) != True:
                    response = JSONResponse(failureResponse('API_RATE_LIMIT_EXCEEDED'))
                elif self.customEndpointCheck(request, requesteData) != True:
                    response = JSONResponse(failureResponse('INVALID_ENDPOINT'))
                else:
                    response = await call_next(rawRequest)
            return response
        except Exception as e:
            logger.error(f"Unhandled exception in middleware: {str(e)}")
            traceback.print_exc()
            return JSONResponse(failureResponse('ACCESS_ERROR'))