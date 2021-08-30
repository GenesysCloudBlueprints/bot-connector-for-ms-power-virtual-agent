import http.client
import json
import time
import logging
import bot_sessions

# the token also acts as the bot id
MS_BOT_AUTHORIZATION_SECRET = "Bearer "

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

def lambda_handler(event, context):
    logger.info('Event:')
    logger.info(json.dumps(event))
    #print('event:' + str(event))
    
    if 'body' not in event or type(event['body']) is not dict:
        return {
            "errorInfo":
                {
                    "errorCode": 500,
                    "errorMessage": "event input is malformed"
                }
        }

    if 'headers' not in event or type(event['headers']) is not dict:
        return {
            "errorInfo":
                {
                    "errorCode": 500,
                    "errorMessage": "event input is malformed"
                }
        }

    if 'Authorization' not in event['headers']:
        print("bad secret - " + str(event))
        return {
            "errorInfo":
                {
                    "errorCode": 403,
                    "errorMessage": "Unauthorized secret",
                    "event": str(event),
                }
        }

    try:
        event_body = event['body']
        logger.info('Body:')
        logger.info(json.dumps(event))

        bot_session = make_or_touch_bot_session(event_body)
        print ('bot_session:' + str(bot_session))

        if 'serviceSessionId' in bot_session:
            print("serviceSessionId - " + bot_session['serviceSessionId'])
            session_id = bot_session['serviceSessionId']
        else:
            # Didn't have a session - we'll treat this as a new one
            print("Didn't have a session - we'll treat this as a new one")

        print ('Calling create_conversation_session()')
        session_id = create_conversation_session(bot_session)

        print("Calling send_text_message(" + str(event_body) + ", " + session_id + ")")
        response = send_text_message(event_body, session_id)

        logger.info('Response:')
        logger.info(json.dumps(response))

        result = convert_ms_response_to_byob(response, bot_session)
        return result
    except SyntaxError as error:
        print("SyntaxError - " + str(error.text))
        return {
            "errorInfo":
            {
                "errorCode": "400",
                "errorMessage": error.text,
                "event": str(event)
            }
        }
    except Exception as ex:
        print("Exception - " + str(ex))
        return {
            "errorInfo":
                {
                    "errorCode": "400",
                    "errorMessage": ex,
                    "event": str(event)
                }
        }

def make_or_touch_bot_session(event):
    """
    Create the bot session if it doesn't exist.. or else update it by incrementing its touchCount and return it for
    subsequent accesses.
    """
    bot_session = dict()
    bot_session['botSessionId'] = event['botSessionId']
    bot_session['expireAt'] = bot_sessions.aws_expire_at_seconds(60 * 5)  # convert min to sec here

    bot_session = bot_sessions.BYOB2MSHandlerSessions.update_session(bot_session, False)
    if bot_session is None:
        raise SyntaxError('bot session creation failed')

    return bot_session

def convert_ms_response_to_byob(ms_response, bot_session):
    """
    {
        "replymessages":
        [
            { "type":"text", "text":"your cookie is ordered" },
            { "type":"structured", "text": "For those who only know plain text", "content" : [ {"contentType": "foo", "content": "response2" }, {"contentType": "bar", "content": "response3"}
        ],
        "intent" : "orderCookie",
        "confidence" : "0.5",
        "botState": "COMPLETE",
        "slotValues":
        {
            "slotString" : "value1",
            "slotStringCollection" : [ "alpha", "beta", "delta" ]
            "slotInteger" : 27,
            "slotDuration" : "P1D",
            "slotDecimal" : 3.14,
            "slotBoolean" : True,
            "slotDateTime" : "1955-11-05T12:00:00",
            "slotCurrency" : { "amount" : "5.00", "code" : "USD" },
            "slotCurrency2" : "17.00|USD",
        },
        "errorInfo":
        {
            "errorCode": "xxx",
            "errorMessage": "A description of the error"
        }
    }
    """

    if 'activities' not in ms_response:
        raise SyntaxError('No activities in response')

    # Initialize byob object
    rv = dict()
    rv['replymessages'] = list()
    # confidence isn't returned by the virtual agent - so we'll treat a success as 1
    rv['confidence'] = 1
    
    responses = ms_response['activities']

    if len(responses) == 0:
        print('No activities in response')
        rv['botState'] = 'Failed'
        return rv

    # Loop through responses
    for response in responses:
        
        if 'type' not in response:
            print('No type in response')
            rv['botState'] = 'Failed'
            return rv
        
        if response['type'] == 'message':
            print('message')
            # This is a return message to be sent out to the user
            rv['botState'] = 'MoreData'
            rv['replymessages'].append(convert_text_response_to_message_format(response))
            # Likewise with intent, interim slot values aren't returned, we get this back when the conversation is over
            #rv['slotValues'] = None
        elif response['type'] == 'event' and response['name'] == 'handoff.initiate':
            print('handoff.initiate')
            # To handle end of conversation detection AND capture the slots - MS will return this data as part of a
            # Transfer to Agent action - set that at the end of the chat and the event will be caught here to properly
            # handle termination detection back to BYOB
            rv['botState'] = 'Complete'
            #rv['replymessages'].append(convert_text_response_to_message_format(response))
            rv['intent'] = get_intent_from_transfer_to_action_event(response)
            rv['slotValues'] = get_slot_values_from_transfer_to_action_event(response)
        else:
            rv['botState'] = 'Failed'

    if 'intent' not in rv:
        rv['intent'] = 'None'
        
    logger.info('byob response:')
    logger.info(json.dumps(rv))
        
    return rv

def get_intent_from_transfer_to_action_event(response):
    """
    On a transfer to action event, MS will return the current context of the chat - including the intent name
    This method will pull that value out of the response
    """
    # Variables will be stored in a dict in the response:
    if 'value' in response:
        if 'va_LastTopic' in response['value']:
            return response['value']['va_LastTopic']

    return None

def get_slot_values_from_transfer_to_action_event(response):
    """
    On a transfer to action event, MS will return the context of the chat which includes all the slot values
    This method will crack out those values
    """
    rv = {}
    if 'value' in response:
        for key in response['value']:
            # MS will return both user defined and internal context values in this set - internal variables are
            # helpfully prefixed with 'va_' so we'll presume that any variable that's NOT prefixed with 'va_' is meant
            # to be returned as a detected slot!
            if key.startswith('va_'):
                rv[key] = response['value'][key]

    return rv

def get_first_response_type(generic_response):
    if generic_response is not None:
        for x in generic_response:
            return x['response_type']

    return None

def convert_text_response_to_message_format(response):
    new_msg = dict()
    if 'textFormat' in response and response['textFormat'] == 'markdown':
        if 'text' in response:
            new_msg['type'] = 'text'
            new_msg['text'] = response['text']

    return new_msg

def convert_entities_to_slots(response_entities):
    rv = dict()

    for entity in response_entities:
        rv[entity['entity']] = entity['value']

    return rv

def create_conversation_session(bot_session):
    uri_path = "/v3/directline/conversations"

    headers = {
        "Authorization": MS_BOT_AUTHORIZATION_SECRET
    }

    data = do_http_call("POST", "directline.botframework.com", uri_path, body=None, headers=headers)

    responsevalue = json.loads(data)

    # The response value comes back with some additional data about initial slot state but I don't think we need
    # anything else
    if 'conversationId' not in responsevalue:
        raise SyntaxError("No 'conversationId' returned from MS Bot")

    # Update our bot_session with the necessary values
    session_id = responsevalue['conversationId']
    bot_session['serviceSessionId'] = session_id

    bot_session = bot_sessions.BYOB2MSHandlerSessions.update_session(bot_session)

    return session_id

def send_text_message(event_body, session_id):
    # convert the inbound input_text into ms' format
    if 'inputMessage' in event_body and type(event_body['inputMessage']) is dict \
            and 'text' in event_body['inputMessage']:
        input_msg = dict()
        input_msg['locale'] = 'en-US'
        input_msg['type'] = 'message'
        input_msg['text'] = event_body['inputMessage']['text']
        input_msg['from'] = dict()
        input_msg['from']['id'] = 'genesys-bot-connector-user'

        uri_path = "/v3/directline/conversations/" + session_id + "/activities"

        headers = {
            "Authorization": MS_BOT_AUTHORIZATION_SECRET,
            "Content-Type": "application/json"
        }

        input_str = json.dumps(input_msg)

        print('uri_path:' + str(uri_path))
        print('input_str:' + str(input_str))
        print('headers:' + str(headers))

        data = do_http_call("POST", "directline.botframework.com", uri_path, body=input_str, headers=headers)
        print('data:' + str(data))

        responsevalue = json.loads(data)

        # We'll get a message id back
        if 'id' not in responsevalue:
            raise SyntaxError("No 'id' returned from MS Bot")

        # The ID is of the format - session_id | message_id - we need to break out the message id to get the response
        id_response = responsevalue['id'].split('|', 2)

        if len(id_response) != 2:
            raise SyntaxError("returned id is not valid")

        message_id = id_response[1]

        # quick turn arounds seem to make MS unhappy and fail the get - sleep a bit to get the response successfully
        time.sleep(0.5)

        # Now retrieve the message for the response
        uri_path = "/v3/directline/conversations/" + session_id + "/activities?watermark=" + message_id

        data = do_http_call("GET", "directline.botframework.com", uri_path, body=None, headers=headers)

        return json.loads(data)
    
def http_client_request_with_raise(connection, method, url, body=None, headers={}, *, encode_chunked=False, log_body_on_error=False):
    """
    A helper method that wraps the native http.client.HTTPSConnection::request() method and transforms the
    HTTP result into an exception if it's a non-2xx status, which is generally what callers want.  It returns
    the full response object if it's a 2xx range status

    :param connection: an instance of an http.client.HTTPSConnection object
    :param method: the HTTP method, such as GET/PUT/POST/etc
    :param url: the URL to request, which should begin with a leading slash
    :param body: the body to send, or None to omit the body
    :param headers: headers to send, or None to omit extra headers
    :param encode_chunked: True or False based on your chosen encoding style
    :param log_body_on_error: if True, print out the body (if available) on error
    :return: the HTTP response object for 2xx statuses
    """
    if connection is None or type(connection) is not http.client.HTTPSConnection:
        # You're likely mis-using this method.. it's intended to be used with an HTTPSConnection object
        raise SyntaxError("Bad HTTPS connection object in request")

    connection.request(method, url, body=body, headers=headers, encode_chunked=encode_chunked)
    res = connection.getresponse()
    if res is None:
        raise SyntaxError("HTTPS request returned no response")

    if 200 <= res.status <= 299:
        # This is good, a success. return the res object
        return res

    if log_body_on_error:
        # NOTE that we don't read the body unless we're asked to, because the body can only be read once. If the
        # caller is going to read the body then he can't let us do it here.
        try:
            body = res.read().decode('utf-8')
            print(body)
        except Exception as ex:
            body = 'Cannot ready body, exception ' + str(ex)
            print(body)

    # A non-2xx response
    if res.status == 429:  # Too Many Requests
        raise SyntaxError("Too Many Requests")
    if res.status == 503:  # Service Unavailable
        raise SyntaxError("Service Unavailable")
    if res.status == 504:  # Gateway Timeout
        raise SyntaxError("Gateway Timeout")
    raise SyntaxError(res)

def do_http_call(method, uri_host, uri_path, body=None, headers={}):
    conn = None
    try:
        conn = http.client.HTTPSConnection(uri_host, timeout=11)

        res = http_client_request_with_raise(conn, method, uri_path, body=body, headers=headers,
                                             log_body_on_error=True)

        # res will get deleted on conn close (in finally below) we copy it to data here
        data = res.read().decode('utf-8')

        return data

    except SyntaxError:
        raise
    except Exception as ex:
        raise SyntaxError(str(ex))
    finally:
        # Attempt to close the connection, we're done with it
        if conn is not None:
            try:
                conn.close()
            except Exception:
                # Ignore exceptions closing the connection - make this a best effort
                pass
