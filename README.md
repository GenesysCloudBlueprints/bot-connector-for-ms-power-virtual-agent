# bot-connector-for-ms-power-virtual-agent

This Genesys Cloud Developer Blueprint provides instructions for deploying a Microsoft Power VA bot in Genesys Cloud. The Genesys Bot Connector is used here to provide an API for the bot to connect to, but a direct link between Genesys Cloud and the bot is not possible. For this scenario to work, an application (known as the Bot Interpreter and represented by the Lambda function in the diagram) needs to be in between Genesys Cloud and Power VA. This application takes the message from the customer using Messenger (known as the utterance) from Genesys Bot Connector and changes the format before sending out a HTTP request to Power VA for NLU. The return message is also converted by the Bot Interpreter to match the postUtterance API provided by Genesys Bot Connector.

![Flowchart for the bot connector solution](blueprint/images/flowchart_bot_connector.png "Flowchart for the bot connector solution")
