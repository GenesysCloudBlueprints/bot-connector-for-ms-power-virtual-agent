---

title: Use Web Messaging with Genesys Bot Connector and Microsoft Power VA (Virtual Assistant)
author: Marc Sassoon and Pierrick Lozach
indextype: blueprint
icon: blueprint
image: 
category: 3
summary: |
  This Genesys Cloud Developer Blueprint explains how to deploy a Microsoft Power Virtual Agent (VA) bot in Genesys Cloud. The blueprint solution uses Genesys Bot Connector that provides the API to connect to the bot. The Genesys Bot Connector acts as the link between Genesys Cloud and the bot.
---

This Genesys Cloud Developer Blueprint explains how to deploy a Microsoft Power Virtual Agent (VA) bot in Genesys Cloud. The blueprint solution uses Genesys Bot Connector that provides the API to connect to the bot. The Genesys Bot Connector acts as the link between Genesys Cloud and the bot. 

## Scenario

Customers might use different third-party chatbots in their business. Genesys Cloud supports and provides interface systems for selected chatbot providers such as AWS and Google. Many new chatbot vendors are fast-growing in the market. Customers want to bring in third-party bots in the Architect message flows and populate the bot list.

## Solution
Genesys Bot Connector provides the API to call third-party bots in an Architect message flow. The blueprint showcases how to connect to the Microsoft Power VA bot in Genesys Cloud using the AWS services:

1. Create an application using AWS Lambda functions. The application known as the Bot Interpreter acts in between Genesys Cloud and Power VA. 
2. Create a chatbot with topics and entities in Microsoft Power VA.
3. Configure a Messenger in your website.

The Lambda application receives the utterances from the Messenger through Genesys Bot Connector. The Lambda application acts in between Genesys Cloud and the Power VA. The application changes the format of the request before sending out an HTTP request to Power VA for Natural Language Understanding (NLU). It also converts the response message received from Power VA to match the postUtterance API that is provided by the Genesys Bot Connector.

The following illustration showcases the outline of the blueprint solution.

![Flowchart for the bot connector solution](images/bot-wm-aws.png "Flowchart for the bot connector solution")

## Contents
* [Solution components](#solution_components "Goes to the Solutions components section")
* [Prerequisites](#prerequisites "Goes to the Prerequisites section")
* [Implementation steps](#implementation_steps "Goes to the Implementation steps section")
* [Additional resources](#additional_resources "Goes to the Additional resources section")

## Solution components

* **Genesys Bot Connector** - The Genesys Bot Connector configuration allows your third-party bots to interact conversationally with customers. A set of RESTful APIs that allows you to connect to any bot platform to send and receive utterances.
*  **Architect flow** - A flow in Architect, a drag and drop web-based design tool, dictates how Genesys Cloud handles inbound or outbound interactions.
* **Microsoft Azure account** - A cloud computing platform that provides a variety of cloud services for building, testing, deploying, and managing applications through Microsoft-managed data centers. Microsoft Azure hosts the Power VA bot.
* **AWS** - Amazon Web Services, a cloud computing platform that provides a variety of cloud services such as computing power, database storage, and content delivery. AWS hosts Genesys Cloud.
* **AWS Lambda** - A serverless computing service for running code without creating or maintaining the underlying infrastructure. In this solution, the Lambda function acts as the bot interpreter application that is written in Python.
* **Amazon API Gateway** - An AWS service for using APIs in a secure and scalable environment. In this solution, the API Gateway exposes a REST endpoint that is protected by an API key. Requests that come to the API Gateway are forwarded to an AWS Lambda.
* **REST API client** - A method or tool used to invoke REST API services that are exposed for communication. In this solution, you send an HTTP PUT request with JSON payload to the Bot Connector API that creates the bot list. For example, Postman, YARC or any other tool to send REST API requests and receive responses.
* **Website with Messenger** - A website with a message window to interact with the bot. It is required to test the solution.
  

## Prerequisites

### Specialized knowledge

* Administrator-level knowledge of Genesys Cloud
* Experience using the Genesys Cloud API
* Experience using Microsoft Power VA
* Experience using Architect flows
* Knowledge about adding scripts to HTML pages

### Genesys Cloud account

* A Genesys Cloud license. For more information, see [Genesys Cloud pricing](https://www.genesys.com/pricing "Opens the Genesys Cloud pricing page") on the Genesys website.
* The Master Admin role in Genesys Cloud. For more information, see [Roles and permissions overview](https://help.mypurecloud.com/?p=24360 "Opens the Roles and permissions overview article") in the Genesys Cloud Resource Center.

### AWS account

* An administrator account with permissions to access the following services:
	* AWS API Gateway
	* AWS Lambda

### Microsoft Azure account
* Admininstrator-level role for Microsoft Azure to create the bot in Power VA.

## Implementation steps

* [Clone the GitHub repository](#clone-the-github-repository "Goes to the Clone the GitHub repository section")
* [Create a Power VA bot](#create_a_power_va_bot "Goes to the Create a Power VA bot section")
* [Configure AWS](#configure_aws "Goes to the Configure AWS section")
* [Configure Genesys Cloud](#configure_genesys_cloud "Goes to the Configure Genesys Cloud section")
* [Load the Power VA bot to the Genesys Cloud bot list](#load-the-power-va-bot-to-the-genesys-cloud-bot-list "Goes to the Load the Power VA bot to the Genesys Cloud bot list section")
* [Create an Architect Flow](#create_architect_flow "Goes to the Create an Architect Flow section")
* [Set up Web Messaging and test the bot](#set-up-web-messaging-and-test-the-bot "Goes to the Set up Web Messaging and test the bot section")

### Clone the GitHub repository

1. Clone the GitHub repository [GCBotConnectorPowerVa repository](https://github.com/msassoon/GCBotConnectorPowerVa "Opens the GCBotConnectorPowerVa GitHub repository") to your machine. The `GCBotConnectorPowerVA/src` folder includes the solution-specific Python files:
	* `Automate_BYOB2MS.py`
	* `bot_sessions.py`

### Create a Power VA bot

1. Go to [Microsoft Power Virtual Agents](https://aka.ms/TryPVA "Opens the Microsoft Power Virtual Agents page") and create a bot. For more information, see [Create your first bot](https://docs.microsoft.com/en-gb/power-virtual-agents/fundamentals-get-started#create-your-first-bot "Opens the Create your first bot page") in Microsoft Power Virtual Agents documentation.
2. Create at least one [topic](https://docs.microsoft.com/en-gb/power-virtual-agents/authoring-create-edit-topics "Opens the Create and edit topics page") or intent that you want to use later.
3. [Publish](https://docs.microsoft.com/en-gb/power-virtual-agents/publication-fundamentals-publish-channels "Opens the Publish your bot page") your bot at least once.
4. Navigate to **Manage** > **Security** and select **Web channel security**.
5. Copy the Secret 1 token.

	![Create the bot security key](images/PowerVaSecurity.png "Create the bot security key")
6. Open the `Automate_BYOB2MS.py` file and replace the `MS_BOT_AUTHORIZATION_SECRET` value with `Bearer {<Secret 1>}`. For example:
		`MS_BOT_AUTHORIZATION_SECRET = "Bearer aNieNrIk.YcKFpSi-nPShwuL9Jhji00-218c2f2P8xDCSa"`
7. In the Power VA URL, copy the URL part after `/bots/` for later. For example, if the Power VA URL is https://web.powerva.microsoft.com/environments/Default-785ce69c-90cf-4dc7-a882-eaf334d1d25g/bots/b80cde13-489d-4eab-acad-26893fd9rft1/, then copy and save the ID `b80cde13-489d-4eab-acad-26893fd9rft1`. You use this URL part for the bot list.

### Configure AWS Services

### Set up Amazon DynamoDB

1. Log into the AWS Management Console.
2. Create a table in Amazon DynamoDB service. Enter `automate-byob2ms-sessions` as the table name. If you change the table name, then ensure to update the parameter `DYNAMODB_SESSIONS_TABLE_NAME` in Line 10 of the `bot_sessions.py` file. Use `botSessionId` as the Primary Key for the table.

### Create a function using AWS Lambda

1. In the AWS Management Console, select Lambda from AWS services.
2. Click **Create function**.
3. Give a significant name for the function, for example, `MSGCConnector`.
4. Select **Python 3.x** for **Runtime**.
5. Upload both the python files from the `\src` directory. To ensure that the code is copied to AWS, click **Deploy**.
6. Add the **AmazonDynamoDBFullAccess** policy to the role used by the Lambda function. You can also restrict the permissions to the `automate-byob2ms-sessions` table only.

	![Set Permissions](images/DynamoDBPermissions.png "Set Permissions")

### Add an Amazon API Gateway to the Lambda function

Add an Amazon API gateway to your Lambda function.

1. Select the function in the Lambda console.
2. Under **Functional overview**, click **Add Trigger**.
   ![Add Trigger](images/TriggerAdding.png "Add Trigger")
3. Select **API Gateway** and the following options for API:
   * API - Create an API
   * API Type - REST API
   * Security - Open (for testing)
4. Click **Add**.
5. To edit the newly added API Gateway, select the API Gateway from the list under **Functional overview**.
6. Select the root (/) of the **Resources** and choose **Actions** > **Create Resource**.
   ![Create API Gateway Resource](images/CreateResource.png "Create API Gateway Resource")
7. Name the resource as `postutterance` and click **Create Resource**.
   ![Create Resource](images/create-resource.png "Create Resource")
8. Choose **Actions** > **Create Method**. Select **POST** from the list and click the check mark to confirm.
   ![Add POST Method to Gateway](images/MethodSettings.png "Add POST Method to Gateway")
9.  Select **Lambda Function** as the Integration type, enter the function name, and click **Save**.
	![Trigger Lambda Settings](images/LambdaSettings.png "Trigger Lambda Settings")

10. Click **Ok**.

11. Select **Integration Request** and expand **Mapping Templates**.
        
12. Click **Add mapping template** and enter `application/json` as the MIME-type for the **Content-Type**. Click the create icon next to the box.
    
	![Set Mapping Template](images/MappingTemplate.png "Set Mapping Template")

13. Select **Never** for **Request body passthrough** option.
    
14. Scroll down and enter the following JSON request into the code box and click **Save**:
	```JSON	
	{
		"body": $input.json('$'),
		"headers": {
			#foreach($param in $input.params().header.keySet())
			"$param": "$util.escapeJavaScript($input.params().header.get($param))"
			#if($foreach.hasNext),#end
			#end
		}
	}
	```
15. For the POST method, choose **Actions** > **Deploy API**.
    
	![Deploy API Gateway](images/DeployAPI.png "Deploy API Gateway")

16. Go back to the Lambda function. Under the **Configuration** tab, select **Triggers**. Expand the **Details** section and make a note of the API endpoint URL for later use.
    
	![Trigger URL](images/TriggerURL.png "Trigger URL")


### Configure Genesys Cloud

### Create Genesys Bot Connector integration

1. Click **Admin**.
2. Under **Integrations**, click **Integrations**.
3. Search for Genesys Bot Connector and click **Install**.
4. Provide a name for the integration and click the **Configuration** tab.
5. Click **Properties**.
6. Enter the endpoint URL that you saved from the Amazon API Gateway in the [Bot Connector Handle Utterance URI](#create-a-power-va-bot "Opens the Create a Power VA bot section") property.
For example, `https://accountname.execute.api.eu.west-1.amazonaws.com/default/postutterance`
	
	![Post Utterance Setting](images/PostUtteranceSettings.png "Post Utterance Setting")
1. Click the **Credentials** tab and add access credentials for the third-party bot. To connect to the Power VA bot that you created earlier, use the [Bearer value](#create-a-power-va-bot "Opens the Create a Power VA bot section") that you noted. You can also use any authorization headers that you want to send.
2. Click **Configure** and the Configure Credentials dialog opens.
   1. Click **Add Credential Field**.
   2. Enter the appropriate access token for the bot.
      * Field Name  - Authorization
      * Value - "Bearer *your secret value*"
  	![Configure Credentials](images/Credentials.png "Configure Credentials")
   3. Click **Ok**.
3. To activate the integration, click the Status toggle to change it from **Inactive** to **Active**. Click **Yes**.
4.  Make a note of the integration ID from the URL for later use.

### Create a custom role in Genesys Cloud

Create a customized role in Genesys Cloud and assign the **textbots > All Permissions** permission. Assign this role to your Genesys Cloud account.

For more information about roles and permissions, see [Roles and permissions overview](https://help.mypurecloud.com/articles/about-roles-permissions/ "Opens the Roles and permissions page") and [Assign roles, divisions, licenses, and add-ons
](https://help.mypurecloud.com/articles/assign-roles-divisions-licenses-and-add-ons/ "Opens the Assign roles, divisions, and add-ons page") in the Genesys Cloud Resource Center.

![GC Permissions](images/GCPermissions.png "GC Permissions")

### Load the Power VA bot to the Genesys Cloud bot list

Use any REST API client, such as Postman, to send the HTTP PUT request to Genesys Cloud. The essential details to send an HTTP PUT request in a REST API client are:
* Microsoft Power VA bot ID - The bot ID that you noted when you created the [Power VA bot](#create-a-power-va-bot "Opens the Create a Power VA bot section").
* Access token from Genesys Cloud to authenticate against the API.

1. Send the PUT request to the Genesys Cloud API `https://api.mypurecloud.ie/api/v2/integrations/botconnector/<your Genesys bot connector integration ID>/bots`. Ensure that the topics and entities are correct in the payload.

	```
	PUT https://api.mypurecloud.ie/api/v2/integrations/botconnector/{YOUR GENESYS BOT CONNECTOR INTEGRATION ID}/bots
	Authorization: bearer {YOUR GC ACCESS TOKEN}
	Content-Type: application/json

	{
	"chatBots": [
		{
		"id": "{PVA BOT ID}",
		"name": "{DISPLAY NAME}",
		"versions": [
			{
			"version": "Delta",
			"supportedLanguages": [
				"en-us",
				"es"
			],
			"intents": [
				{
				"name": "Check Stock",
				"slots": {
					"Slot1 ": {
					"name": "Slot1",
					"type": "String"
					}
				}
				},
				{
				"name": "Escalate",
				"slots": {
					"Slot2": {
					"name": "Slot2",
					"type": "String"
					}
				}
				}
			]
			}
		]
		}
	]
	}
	```
2. The HTTP `204 No Content` status response code indicates that the request was successful.
The bot is added to the bot list and Genesys Cloud Architect uses this list to populate the bot details.

### Create an Architect flow

1. In Genesys Cloud, navigate to **Admin** > **Architect**.
2. In Architect, create an Inbound Message flow. For more information, see [Add an inbound message flow](https://help.mypurecloud.com/articles/add-inbound-message-flow/ "Opens the Add an inbound message flow page") in the Genesys Cloud Resource Center.
3. Navigate to **Toolbox** > **Bot** and drag a **Call Bot Connector** action to the editor.

	![GC Toolbox](images/Toolbox.png "GC Toolbox")
4. Configure the action for the **Name**, **Bot Integration**, and **Bot Version** as specified in the REST API call.

	![Call Bot Connector block](images/CallConnector.png "Call Bot Connector block")
5. Complete the rest of the flow as required. For more information, see [Call Bot Connector action](https://help.mypurecloud.com/articles/call-bot-connector-action/ "Opens the Call Bot Connector action page") in the Genesys Cloud Resource Center.

	![Finish Architect Flow](images/ArchitectFlow.png "Finish Architect Flow")

### Set up Web Messaging and test the bot

1. Configure a messenger to interact with the bot. For more information, see [Configure Messenger](https://help.mypurecloud.com/articles/configure-messenger/ "Opens the Configure Messenger page") in the Genesys Cloud Resource Center.
2. Create a messenger deployment with the Architect flow created for the bot. For more information, see [Deploy Messenger](https://help.mypurecloud.com/articles/deploy-messenger/ "Opens the Deploy Messenger page") in the Genesys Cloud Resource Center.
   ![Messenger Deployment](images/MessengerDep.png "Messenger Deployment")
3. To deploy the Messenger snippet to your website, copy the snippet under **Deploy your snippet** and paste the snippet to the `<head>` tag of all of your webpages. The `index.html` page in the code has a sample to use.

	![Messenger](images/Messenger.png "Messenger")
	

## Additional resources

* [About Genesys Bot Connector](https://help.mypurecloud.com/articles/about-genesys-bot-connector/ "Opens the About Genesys Bot Connector page") in Genesys Cloud Resource Center
* [About Web Messaging](https://help.mypurecloud.com/articles/about-web-messaging/ "Opens the About Web Messaging page") in the Genesys Cloud Resource Center
* [AWS Lambda](https://aws.amazon.com/translate/ "Opens the AWS Lambda page") in the Amazon featured services
* [Power Virtual Agents Overview](https://docs.microsoft.com/en-us/power-virtual-agents/fundamentals-what-is-power-virtual-agents "Opens the Microsoft Power Virtual Agents documentation") in the Microsoft Power VA documentation
* [Web Messaging](https://help.mypurecloud.com/articles/web-messaging-overview/ "Opens the Web Messaging overview page") in the Genesys Cloud Resource Center