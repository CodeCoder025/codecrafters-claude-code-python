#Tbh this is much more pythonic than i expected. Its all about formatting and understanding JSONs and the chat & choice objects

import argparse
import os
import sys
import ast
import json
import subprocess

from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", default="https://openrouter.ai/api/v1")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("-p", required=True)
    args = p.parse_args()

    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    messages = [{"role":"system","content":"You have access to the following skills: \n\n Apple: Deploys the apple service to production\nGrape: Runs the grape test suite and reports failures"},
                {"role": "user", "content": args.p}]
    if messages[1].get("content").startswith("/"):
        if messages[1].get("content").count(" ") == 0:
            skillInvoked = messages[1].get("content")[1:len(messages[1].get("content"))]
        else:
            skillInvoked = messages[1].get("content").split(" ")[0][1:len(messages[1].get("content"))]
        with open(".claude/skills/%s/SKILL.md"%skillInvoked,"r") as i:
            skillFileContent = i.read()
            bodyAfter = skillFileContent.find("---",3)
            skillFileBody = skillFileContent[bodyAfter+3:]
            messages[1]["content"] = skillFileBody

    #an overview of all skills available (just the name and description, not the body) is given to the model as a system prompt
    
    while True:
        chat = client.chat.completions.create(
            model="anthropic/claude-haiku-4.5",
            messages=messages,
            tools=[{
                    "type": "function",
                    "function": {
                        "name": "ReadFile",
                        "description": "Read and return the contents of a file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "The path to the file to read"
                            }
                        },
                        "required": ["file_path"]
                        }
                    }
                    },
                    {
                        "type":"function",
                        "function":{
                            "name":"WriteFile",
                            "description":"Write content into a file",
                            "parameters":{
                                "type":"object",
                                "required":["file_path","content"],
                                "properties":{
                                    "file_path":{
                                        "type":"string",
                                        "description":"path of file to write to"},
                                    "content": {
                                        "type":"string",
                                        "description":"contents to write into the file"
                                    }
                                }
                            }
                        }
                    },
                    {
                        "type":"function",
                        "function":{
                            "name":"Bash",
                            "description":"run a shell command",
                            "parameters":{
                                "type":"object",
                                "required":["command"],
                                "properties":{
                                    "command":{
                                        "type":"string",
                                        "description":"the command to execute"
                                    }
                                }
                            }
                        }
                    }]
        )

        if not chat.choices or len(chat.choices) == 0:
            raise RuntimeError("no choices in response")
        elif chat.choices[0].message.tool_calls is None:
            messages.append({"role":"assistant","content":chat.choices[0].message.content})
            print(chat.choices[0].message.content) #agent run can end when it returns a response with no more tool calls left
            break
        else:
            messages.append(chat.choices[0].message) #append agent reply to message string
            for i in chat.choices[0].message.tool_calls:
                tool_call_id = i.id
                if i.function.name == "ReadFile":
                    arguments = i.function.arguments #choices is a python object by itself! It is not a json. To retrieve values within a choice object, use "."
                    arguments = ast.literal_eval(arguments) #converts a "dict" into a dict
                    filePath = arguments.get("file_path")
                    with open(filePath, "r") as p: #opens file from local machine
                        fileContents = p.read()
                        messages.append({"role":"tool","tool_call_id":tool_call_id,"content":fileContents}) #append result of tool call to message string
                if i.function.name == "WriteFile":
                    arguments = i.function.arguments
                    arguments = ast.literal_eval(arguments)
                    filePath = arguments.get("file_path")
                    writeContent = arguments.get("content")
                    with open(filePath, "w") as q:
                        q.write(writeContent)
                        with open(filePath, "r") as r:
                            newFileContent = r.read()
                        messages.append({"role":"tool","tool_call_id":tool_call_id,"content":"Write tool successful! File contents: %s"%newFileContent})
                if i.function.name == "Bash":
                    arguments = ast.literal_eval(i.function.arguments)
                    command = arguments.get("command")
                    result = subprocess.run(command, shell = True, capture_output = True, text = True)
                    if result.returncode == 0:
                        messages.append({"role":"tool","tool_call_id":tool_call_id,"content":result.stdout})
                    elif result.returncode == 1:
                        messages.append({"role":"tool","tool_call_id":tool_call_id,"content":result.stderr})


            
if __name__ == "__main__":
    main()
