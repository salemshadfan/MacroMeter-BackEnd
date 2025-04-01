import openai
import base64
import json
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import resources_pb2, service_pb2, service_pb2_grpc
from clarifai_grpc.grpc.api.status import status_code_pb2
import ast
import re
from dotenv import load_dotenv
import os

load_dotenv()

GPT_API_KEY = os.getenv("OPENAI_API_KEY")
PAT = 'cace4a264b674174b6587c79a555c4ea'
USER_ID = 'clarifai'
APP_ID = 'main'


MODEL_ID = 'food-item-v1-recognition'
MODEL_VERSION_ID = 'dfebc169854e429086aceb8368662641'

client = openai.OpenAI(api_key=GPT_API_KEY)

def decode_base64_to_bytes(base64_str):
    return base64.b64decode(base64_str)


def encode_image_to_base64(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_image(image_data):
    channel = ClarifaiChannel.get_grpc_channel()
    stub = service_pb2_grpc.V2Stub(channel)

    metadata = (('authorization', 'Key ' + PAT),)
    userDataObject = resources_pb2.UserAppIDSet(user_id=USER_ID, app_id=APP_ID)

    image_data_bytes = decode_base64_to_bytes(image_data)

    post_model_outputs_response = stub.PostModelOutputs(
        service_pb2.PostModelOutputsRequest(
            user_app_id=userDataObject,
            model_id=MODEL_ID,
            version_id=MODEL_VERSION_ID,
            inputs=[
                resources_pb2.Input(
                    data=resources_pb2.Data(
                        image=resources_pb2.Image(
                            base64=image_data_bytes
                        )
                    )
                )
            ]
        ),
        metadata=metadata
    )

    if post_model_outputs_response.status.code != status_code_pb2.SUCCESS:
        print(post_model_outputs_response.status)
        raise Exception("Post model outputs failed, status: " + post_model_outputs_response.status.description)

    output = post_model_outputs_response.outputs[0]
    return output

def GPT_Analyze(prompt, image_data):
    try:
        # Build the messages list.
        # Here we attach the image_data (base64 string) in the same message.
        messages = [
            {
                "role": "user",
                "content": prompt,
                "image": image_data  
            }
        ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=200
        )
        result = response.choices[0].message.content.strip()

        first_line = result.split("\n")[0].lower()
        if "success" not in first_line:
            return "Error: GPT response does not contain 'success' in the first line."

        return result

    except Exception as e:
        return f"Error: {e}"


def generate_gpt_prompt(image_path):
    image_data = encode_image_to_base64(image_path)

    
    response = analyze_image(image_data)

    
    concepts = response.data.concepts
    
    filtered_concepts= []

    for concept in concepts:
        if concept.value > 0.89:  
            filtered_concepts.append(f"{concept.name} {concept.value:.2f}")
   
    prompt = f"""

                Based on the following food items with their confidence scores alongside the image of the meal, please estimate what the food is and the nutritional information (calories, protein, fat, and carbs) for it. 
                Provide the result in the following strict format:
                    success:
                    {{
                        "name": <guessed dish name>,
                        "calories": <value>,
                        "carbohydrates": <value>,
                        "protein": <value>,
                        "fat": <value>   
                    }}
                    
                Here are the food items and their confidence scores:
                {', '.join(filtered_concepts)}
                Consider the top 2 highest confidence scores only.

                Always say success at the very first line before anything else.
                You should return only one food item and provide the nutritional values in key:value format for each item. Do not provide any ranges, extra explanation, or punctuation like periods at the end nor annotations (''' the triple qoutes) for json or anything else.

                """
    return prompt

def convert_to_json(output_str):
    match = re.search(r'\{(.*)\}', output_str, re.DOTALL)

    if match:
        extracted_json = '{' + match.group(1) + '}'
        print(extracted_json)
        data = json.loads(extracted_json)
        return data
    else:
        return "No JSON found in the string."

    




