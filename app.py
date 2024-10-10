# Importing the required libraries
import os

from flask import Flask, jsonify, redirect, url_for, request

from langchain import PromptTemplate
from langchain_huggingface import HuggingFaceEndpoint
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from pydantic import BaseModel
import os, requests, json
from supabase import create_client


# Setting the Hugging Face API Token and Supabase Credentials
HUGGINGFACEHUB_API_TOKEN = open("keys/hf_token").read().strip()
os.environ["HUGGINGFACEHUB_API_TOKEN"] = HUGGINGFACEHUB_API_TOKEN
os.environ["HF_TOKEN"] = HUGGINGFACEHUB_API_TOKEN

supabase_creds = json.loads(open("keys/supabase_creds").read().strip())
supabase_url = supabase_creds["url"]
supabase_key = supabase_creds["key"]

#TechStack Structure
class TechStack(BaseModel):
    techstack: str
    tool_or_language: list[str]

class UserInfo(BaseModel):
    techstacks: list[TechStack]

# Initializing the Hugging Face Endpoint and Output Parser
repo_id="mistralai/Mixtral-8x7B-Instruct-v0.1"
llm = HuggingFaceEndpoint(repo_id=repo_id,
                        max_length=128,
                        temperature=0.5,
                        token=HUGGINGFACEHUB_API_TOKEN)
parser = JsonOutputParser(pydantic_object=UserInfo)
py_parser = PydanticOutputParser(pydantic_object=UserInfo)



app = Flask(__name__)


#Function to insert user data into the Supabase database
def insert_user_data(firstName, lastName, photoUrl, linkedin_url, user_data_json, lat, long):
    print("Inserting User Data")

    supabase = create_client(supabase_url, supabase_key)
    response = (supabase.table('users').insert([{"first_name": firstName, "last_name": lastName, "linkedin_url": linkedin_url, "luma_dp_url": photoUrl, "tech_stack": user_data_json, "lat": lat, "long": long}])
                .execute())
    return response

#Function to get the techstack of the user   
def get_stack(user_data):
    print("prompting")
    question = "What are the skills of the user? Return only the json object. Return the techstack and corresponding (tools or languages) in json object. {format_instructions} If you do not find corresponding techstack for a tools, assume techstack to be others. \n {user_data}"
    prompt = PromptTemplate(
                    template=question, 
                    input_variables= ["user_data"],
                    partial_variables={"format_instructions": parser.get_format_instructions()}
                        )
    linked_in_chain = prompt | llm | parser
    try:
        linked_in_result = linked_in_chain.invoke({"user_data": user_data})
    except:
        del linked_in_chain
        linked_in_chain = prompt | llm | py_parser
        try:
            linked_in_result = linked_in_chain.invoke({"user_data": user_data})
        except:
            del linked_in_chain
            linked_in_chain = prompt | llm
            linked_in_result = linked_in_chain.invoke({"user_data": user_data})
            linked_in_result=linked_in_result.replace("\n", "")
            linked_in_result=linked_in_result.replace("`", "")
            linked_in_result=linked_in_result.replace("json", "")
    return linked_in_result

#Function to get the LinkedIn data of the user
def get_linkedIn_data(linkedin_url, lat, long):
    print("Getting LinkedIn Data")
    scrapin_api_key = open("keys/scrapin_api_key").read().strip()
    api_url = "https://api.scrapin.io/enrichment/profile?apikey="+str(scrapin_api_key)+"&linkedinUrl="+str(linkedin_url)
    print(api_url)
    user_data = requests.get(api_url).json()
    # print(user_data)
    # user_data = json.loads(open("alka_json.json").read().strip())
    firstName = user_data["person"]["firstName"] 
    lastName = user_data["person"]["lastName"]
    photoUrl = user_data["person"]["photoUrl"]
    user_data_json = get_stack(user_data)
    print("User data calculated is :"+ str(user_data_json))
    db_update = insert_user_data(firstName, lastName, photoUrl, linkedin_url, user_data_json, lat, long)
    if db_update:
        return firstName, lastName, photoUrl
    else:
        return "Error"

@app.route('/')
def index():
    return redirect(url_for('scrape_linkedIn'))

@app.route('/scrape_linkedIn', methods=['GET'])
def scrape_linkedIn():
    print("Scraping LinkedIn")
    linkedin_url = request.args.get('linkedIn')
    lat = request.args.get('lat')
    long = request.args.get('long')
    firstName, lastName, photoUrl=get_linkedIn_data(linkedin_url, lat, long)
    return jsonify(firstName, lastName, photoUrl)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80)