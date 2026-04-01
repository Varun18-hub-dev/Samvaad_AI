import json
import boto3
import urllib.request
from boto3.dynamodb.conditions import Key

TOKEN = "can't paste"

dynamodb = boto3.resource("dynamodb")

scholarship_table = dynamodb.Table("scholarships")
user_table = dynamodb.Table("user_profiles")


# ---------- TELEGRAM MESSAGE ----------
def send_message(chat_id, text, keyboard=None, remove=False):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    }

    if keyboard:
        payload["reply_markup"] = json.dumps(keyboard)

    if remove:
        payload["reply_markup"] = json.dumps({
            "remove_keyboard": True
        })

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    urllib.request.urlopen(req)


# ---------- KEYBOARDS ----------

def education_keyboard():
    return {
        "keyboard":[
            ["Engineering","Diploma"],
            ["ITI","Postgraduate"],
            ["10th","12th"]
        ],
        "resize_keyboard":True,
        "one_time_keyboard":True
    }


def category_keyboard():
    return {
        "keyboard":[
            ["General","OBC"],
            ["SC","ST"]
        ],
        "resize_keyboard":True,
        "one_time_keyboard":True
    }


def income_keyboard():
    return {
        "keyboard":[
            ["<1L", "1L-2L"],
            ["2L-3L","3L-5L"],
            [">5L"]
        ],
        "resize_keyboard":True,
        "one_time_keyboard":True
    }


def confirm_keyboard():
    return {
        "keyboard":[
            ["Yes","No"]
        ],
        "resize_keyboard":True,
        "one_time_keyboard":True
    }


# ---------- MAIN HANDLER ----------

def lambda_handler(event, context):

    body = json.loads(event["body"])
    message = body.get("message",{})

    chat_id = str(message["chat"]["id"])
    text = message.get("text","").strip()

    print("User:",chat_id,text)


    # get user profile
    response = user_table.get_item(
        Key={"telegram_id":chat_id}
    )

    user = response.get("Item",{})


    # ---------- START ----------

    if text == "/start":

        user_table.put_item(Item={
            "telegram_id":chat_id,
            "step":"name"
        })

        send_message(chat_id,"👋 Welcome to Scholarship Finder Bot\n\nWhat is your name?")

        return {"statusCode":200}


    # ---------- NAME ----------

    if user.get("step") == "name":

        user["name"] = text
        user["step"] = "education"

        user_table.put_item(Item=user)

        send_message(chat_id,"Select your education level:",education_keyboard())

        return {"statusCode":200}


    # ---------- EDUCATION ----------

    if user.get("step") == "education":

        user["education"] = text
        user["step"] = "category"

        user_table.put_item(Item=user)

        send_message(chat_id,"Select your category:",category_keyboard())

        return {"statusCode":200}


    # ---------- CATEGORY ----------

    if user.get("step") == "category":

        user["category"] = text
        user["step"] = "income"

        user_table.put_item(Item=user)

        send_message(chat_id,"Select your family income:",income_keyboard())

        return {"statusCode":200}


    # ---------- INCOME ----------

    if user.get("step") == "income":

        user["income"] = text
        user["step"] = "confirm"

        user_table.put_item(Item=user)

        profile = f"""
📋 Your Profile

👤 Name: {user['name']}
🎓 Education: {user['education']}
🏷 Category: {user['category']}
💰 Income: {user['income']}

Is this correct?
"""

        send_message(chat_id,profile,confirm_keyboard())

        return {"statusCode":200}


    # ---------- CONFIRM ----------

    if user.get("step") == "confirm":

        if text == "No":

            user_table.put_item(Item={
                "telegram_id":chat_id,
                "step":"name"
            })

            send_message(chat_id,"Let's start again.\n\nWhat is your name?",remove=True)

            return {"statusCode":200}


        if text == "Yes":

            education = user["education"]

            response = scholarship_table.query(
                IndexName="education-index",
                KeyConditionExpression=Key("education_index").eq(education)
            )

            items = response.get("Items",[])

            if not items:
                reply="❌ No scholarships found."
            else:

                reply="🎓 Scholarships You Are Eligible For:\n\n"

                for s in items[:5]:

                    name=s.get("name","Scholarship")

                    amount_min=s.get("amount_min")
                    amount_max=s.get("amount_max")

                    if amount_min and amount_max:
                        amount=f"₹{amount_min} - ₹{amount_max}"
                    else:
                        amount="Not specified"

                    deadline=s.get("deadline","Not specified")
                    link=s.get("application_link","")

                    reply+=f"""🎓 {name}
💰 Amount: {amount}
📅 Deadline: {deadline}
🔗 Apply: {link}

"""

            send_message(chat_id,reply,remove=True)

            return {"statusCode":200}


    return {"statusCode":200}
