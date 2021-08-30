import copy
import datetime

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.client import Config
from botocore.exceptions import ClientError

# some general constants
DYNAMODB_SESSIONS_TABLE_NAME = "automate-byob2ibm-sessions"


def aws_expire_at_seconds(num_seconds):
    """
    Returns an integer value suitable to send to an AWS DynamoDB field for a TTL.  Which ends up being
        "number of seconds elapsed since 12:00:00 AM January 1st, 1970 UTC."
    :param num_seconds:
    :return:
    """
    return int(datetime.datetime.utcnow().timestamp()) + num_seconds


class BYOB2MSHandlerSessions:
    """
    Deal with the state that textquentia keeps to handle bot activity.
    """

    # setup the dynamodb client as a class variable that can be re-used across multiple lambda invokes
    print("setup the dynamodb client")
    config = Config(connect_timeout=2, read_timeout=2, retries={'max_attempts': 2})
    dynamodbClient = boto3.client('dynamodb', config=config)
    print("dynamodb client configured")

    @staticmethod
    def get_textquentia_session(bot_session_id):
        """
        Get a Textquentia session from the dynamoDB table.  The whole session is returned as a dict, or None if
        not found
        :param bot_session_id: the botSessionId in question
        :return: the session as a dict, or None if the session is not found.
        """
        print("Get a Textquentia session from the dynamoDB table")

        try:
            response = BYOB2MSHandlerSessions.dynamodbClient.get_item(TableName=DYNAMODB_SESSIONS_TABLE_NAME,
                                                                      Key={'botSessionId': {'S': bot_session_id}})
            if 'Item' not in response or not response['Item']:
                return None

            # This converts the dynamoDB format (with the {'S': 'mystring'} stuff) to a regular python dict
            deserializer = boto3.dynamodb.types.TypeDeserializer()
            return_val = {k: deserializer.deserialize(v) for k, v in response['Item'].items()}

            return return_val

        except ClientError as ex:
            BYOB2MSHandlerSessions.__convert_boto3_client_error_to_exception(ex)
        except Exception as ex:
            raise SyntaxError(str(ex))
    # --------------------------------------------------------------------------------------------------------

    @staticmethod
    def update_session(bot_session, increment_turn_count=False):
        """
        Get a Textquentia session from the dynamoDB table.  The whole session is returned as a dict, or None if
        not found
        :param bot_session: the botSession in question
        :param increment_turn_count: if true, increment the turn count that's stored in the session
        :return: the session as a dict, or None if the session is not found.
        """
        print("Update the Textquentia session from the dynamoDB table")

        try:
            if type(bot_session) is not dict or 'botSessionId' not in bot_session:
                raise SyntaxError("bot session object is mal-formed")

            expression_attr_names = {'#tc': 'touchCount'}
            update_expr = 'ADD #tc :incrs '
            set_expr = 'SET '
            expr_attr_values = {':incrs': {'N': '1'}}
            expire_at_val = None

            for botField in bot_session:
                if botField == 'botSessionId':
                    pass    # We can ignore this one
                elif botField == 'touchCount':
                    pass    # this is handled via #tc
                elif botField == 'expireAt':
                    expire_at_val = bot_session['expireAt']
                elif botField == 'sessionStart':
                    pass    # Ignore this if we already set it
                elif botField == 'sessionClosed':
                    pass    # This can't be set pro-actively, it's handled for you
                elif botField == 'turnCount':
                    pass    # We can ignore this one, it's handled separately
                else:
                    if len(set_expr) > 4:
                        set_expr = set_expr + ', '
                    set_expr = set_expr + botField + ' = :' + botField
                    expr_attr_values[':' + botField] =\
                        BYOB2MSHandlerSessions.python_to_dynamodb_item(bot_session[botField])

            # Some trickery here:  if the bot session has supplied an expireAt value, we'll set that on a companion
            # dynamo entry as an AWS expiry value which controls closing the session when the expire time hits.  This
            # 'main' entry here always gets a 10-day expire value so we can avoid GDPR impact
            expr_attr_values[':expireAt'] = {'N': str(aws_expire_at_seconds(60*60*24*10))}
            if len(set_expr) > 4:
                set_expr = set_expr + ', '
            set_expr = set_expr + '#expireAt' + ' = if_not_exists(#expireAt, :expireAt)'
            expression_attr_names['#expireAt'] = 'expireAt'
            
            # So we don't have to make multiple calls to dynamo at start, we'll use similar trickery as above to
            # initialize the sessionStart value to the session creation time
            expr_attr_values[':sessionStart'] = {'S': str(datetime.datetime.utcnow())}
            if len(set_expr) > 4:
                set_expr = set_expr + ', '
            set_expr = set_expr + '#sessionStart' + ' = if_not_exists(#sessionStart, :sessionStart)'
            expression_attr_names['#sessionStart'] = 'sessionStart'

            # If the caller has asked us to increment the turn count, then we shall
            if increment_turn_count:
                expression_attr_names['#turns'] = 'turnCount'
                update_expr = update_expr + ', #turns :incrs '

            update_expr = update_expr + set_expr
            
            print('TableName:' + str(DYNAMODB_SESSIONS_TABLE_NAME))
            print('Key:' + str(bot_session['botSessionId']))
            print('ExpressionAttributeNames:' + str(expression_attr_names))
            print('ExpressionAttributeValues:' + str(expr_attr_values))
            print('UpdateExpression:' + str(update_expr))
            
            response = BYOB2MSHandlerSessions.dynamodbClient.update_item(
                    TableName=DYNAMODB_SESSIONS_TABLE_NAME,
                    Key={'botSessionId': {'S': bot_session['botSessionId']}},
                    ExpressionAttributeNames=expression_attr_names,
                    ExpressionAttributeValues=expr_attr_values,
                    UpdateExpression=update_expr,
                    ReturnValues='ALL_NEW')

            if 'Attributes' not in response or not response['Attributes']:
                return None

            # This converts the dynamoDB format (with the {'S': 'mystring'} stuff) to a regular python dict
            deserializer = boto3.dynamodb.types.TypeDeserializer()
            return_val = {k: deserializer.deserialize(v) for k, v in response['Attributes'].items()}

            if expire_at_val is not None and 'touchCount' in return_val and return_val['touchCount'] == 1:
                # This is the first touch of the textquentia session and the session wants to close itself after
                # a delay (represented by 'expire_at_val').  To handle this, we'll make a companion record that has
                # the AWS TTL set to that value.  There's a stream handler in dynamo that will call back into this
                # lambda to handle that
                try:
                    expiry_item = copy.deepcopy(response['Attributes'])
                    if 'touchCount' in expiry_item:
                        del expiry_item['touchCount']
                    if 'sessionClosed' in expiry_item:
                        del expiry_item['sessionClosed']
                    expiry_item['botSessionId'] = {'S': bot_session['botSessionId'] + '-expire'}
                    expiry_item['expirySentinal'] = {'BOOL': True}
                    expiry_item['primaryId'] = {'S': bot_session['botSessionId']}
                    expiry_item['expireAt'] = {'N': str(expire_at_val)}

                    BYOB2MSHandlerSessions.dynamodbClient.put_item(TableName=DYNAMODB_SESSIONS_TABLE_NAME,
                                                                   Item=expiry_item)
                except Exception as ex:
                    # Make this best-effort.  This bot session likely won't time out on its own.  Not end of the world
                    print(f'Exception writing TTL entry for session {bot_session["botSessionId"]}: {ex}')

            return return_val
        except ClientError as ex:
            BYOB2MSHandlerSessions.__convert_boto3_client_error_to_exception(ex)
        except Exception as ex:
            raise SyntaxError(str(ex))
    # --------------------------------------------------------------------------------------------------------

    @staticmethod
    def python_to_dynamodb_item(val):
        """
        Converts a python type to the dynamodb type.  Note detection precedence is important here as
        isinstance(val, int) will return TRUE for boolean values
        https://stackoverflow.com/questions/37888620/comparing-boolean-and-int-using-isinstance
        """
        if isinstance(val, list):
            return {'L': [BYOB2MSHandlerSessions.python_to_dynamodb_item(x) for x in val]}
        if isinstance(val, dict):
            return {'M': {x: BYOB2MSHandlerSessions.python_to_dynamodb_item(val[x]) for x in val}}
        elif isinstance(val, str):
            return {'S': val}
        elif isinstance(val, bool):
            return {'BOOL': val}
        elif isinstance(val, (int, float)):
            return {'N': str(val)}
        else:
            return {'S': str(val)}

    @staticmethod
    def close_textquentia_session(bot_session):
        """
        Mark the textquentia session as closed, so it cannot be re-used
        :param bot_session: the botSession to be deleted
        :return: true if the session was just closed, false if it was not (it might be already closed)
        """
        print("Mark the textquentia session as closed")

        try:
            if type(bot_session) is not dict or 'botSessionId' not in bot_session:
                raise SyntaxError("bot session object is mal-formed")

            bot_session['sessionClosed'] = True

            response = BYOB2MSHandlerSessions.dynamodbClient.update_item(
                TableName=DYNAMODB_SESSIONS_TABLE_NAME,
                Key={'botSessionId': {'S': bot_session['botSessionId']}},
                ExpressionAttributeValues={':trueVal': {'BOOL': True}, ':falseVal': {'BOOL': False}},
                UpdateExpression='SET sessionClosed=:trueVal',
                ConditionExpression='(attribute_not_exists(sessionClosed)) OR (sessionClosed=:falseVal)',
                ReturnValues='ALL_NEW')
            if 'Attributes' not in response or not response['Attributes']:
                return None

            # This converts the dynamoDB format (with the {'S': 'mystring'} stuff) to a regular python dict
            # deserializer = boto3.dynamodb.types.TypeDeserializer()
            # return_val = {k: deserializer.deserialize(v) for k, v in response['Attributes'].items()}

            return True
        except ClientError as ex:
            if ex.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False
            BYOB2MSHandlerSessions.__convert_boto3_client_error_to_exception(ex)
        except Exception as ex:
            raise SyntaxError(str(ex))
    # --------------------------------------------------------------------------------------------------------

    @staticmethod
    def obliterate_session_best_effort(bot_session_id):
        """
        Remove the session completely, without letting it expire naturally
        :param bot_session_id: the botSession to be deleted
        """
        print("Remove the session completely")
        if bot_session_id is None:
            return

        try:
            # Note that if we try to delete the "-expire" item right now, it will get into the STREAMS as a delete
            # and the delete code will not be able to tell that it is our delete here, rather than a TTL expiry. So,
            # before we delete it we have to update it to remove its field that triggers the session close.
            BYOB2MSHandlerSessions.dynamodbClient.update_item(
                TableName=DYNAMODB_SESSIONS_TABLE_NAME,
                Key={'botSessionId': {'S': bot_session_id + '-expire'}},
                UpdateExpression='REMOVE expirySentinal')
            BYOB2MSHandlerSessions.dynamodbClient.delete_item(
                TableName=DYNAMODB_SESSIONS_TABLE_NAME,
                Key={'botSessionId': {'S': bot_session_id + '-expire'}})
        except Exception as ex:
            print(f'Best effort to delete bot session {bot_session_id} expire record failed. Error={ex}')
        try:
            BYOB2MSHandlerSessions.dynamodbClient.delete_item(
                TableName=DYNAMODB_SESSIONS_TABLE_NAME,
                Key={'botSessionId': {'S': bot_session_id}})
        except Exception as ex:
            print(f'Best effort to delete bot session {bot_session_id} failed. Error={ex}')
    # --------------------------------------------------------------------------------------------------------

    @staticmethod
    def convert_dynamodbstreamrecord_to_bot_session(record):
        print("Convert dynamodb stream record to bot session")
        if 'dynamodb' in record and 'OldImage' in record['dynamodb']:
            # This converts the dynamoDB format (with the {'S': 'mystring'} stuff) to a regular python dict
            deserializer = boto3.dynamodb.types.TypeDeserializer()
            return {k: deserializer.deserialize(v) for k, v in record['dynamodb']['OldImage'].items()}
        else:
            return None
    # --------------------------------------------------------------------------------------------------------

    @staticmethod
    def __convert_boto3_client_error_to_exception(client_error):
        """
         Note that when the boto3 client throws a ClientError, it looks something like this for the ex.response:

          {
            'Error':
              {
               'Message': 'The level of configured provisioned throughput for the table was exceeded. Consider
                                       increasing your provisioning level with the UpdateTable API.',
               'Code': 'ProvisionedThroughputExceededException'
              },
            'ResponseMetadata':
              {
               'RequestId': 'C277UO7F6ATOD4HNDB4D7PLNONVV4KQNSO5AEMVJF66Q9ASUAAJG',
               'HTTPStatusCode': 400,
               'HTTPHeaders': {'server': 'Server', 'date': ... },
               'MaxAttemptsReached': True,
               'RetryAttempts': 0
              }
          }
        """

        if client_error.response and client_error.response['Error'] and client_error.response['Error']['Code']:
            if client_error.response['Error']['Code'] == 'ProvisionedThroughputExceededException':
                # Oh no, our client did have some throughput error retries, but apparently that wasn't enough.
                return SyntaxError(str(client_error))
            else:
                # Some other exception has occurred, just throw it
                return SyntaxError(client_error.response['Error']['Message'])
        else:
            # Some other exception has occurred, just throw it
            return SyntaxError(str(client_error))

    @staticmethod
    def get_touch_count(bot_session):
        touch_count = 0
        if 'touchCount' in bot_session:
            touch_count = bot_session['touchCount']

        return touch_count
