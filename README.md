# Regbot
Resource of Regbot


# Setup local environment

1. make sure that python has been already installed on your local
2. clone this repository
3. move to "/azure/function_apps" directory
4. run `ptrhon -m venv venv`
5. run `.\venv\Scripts\activate`
6. run `pip install -r requirements.txt`


# How to deploy function apps

## Prerequisite

1. install vscode extensions related to Azure resource and functions
2. make sure your sidebar like following picture![sidebar](readme_sidebar.png)

## deploy

### source code deploy

1. hover your mouse on "Local Project" and click cloud icon
2. select "az-tak-rnd-adj-genai" --> {target function name}
3. click "yes" on the dialog
4. make sure that Azure console on vscode says that Deploy to App "extractfileinfo" Succeeded (it may take few minutes)
5. make sure that source code on Azure Portal is updated to the latest one (it may take less than 10 minutes)

### update environment variables on function app

1. update local.settings.json with appropriate environment variables
2. click "Upload Local Settings" on target function apps like following picture![upload variable](readme_upload_variable.png)
3. make sure that env variable on Azure Portal is updated to the latest one