import json
import boto3
import urllib.request

TOKEN = "8700438855:AAGVXRgzULdNiGEuoCbrB0mkWb1f4q8K9gQ"

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("scholarships")


def send_message(chat_id, text):

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    data = json.dumps({
        "chat_id": chat_id,
        "text": text
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"}
    )

    urllib.request.urlopen(req)


def lambda_handler(event, context):

    print("EVENT:", event)

    body = json.loads(event["body"])

    chat_id = body["message"]["chat"]["id"]
    text = body["message"].get("text","").lower()

    print("User message:", text)

    # ------------------------------------------------
    # Temporary user profile
    # later this will come from Telegram conversation
    # ------------------------------------------------

    user_profile = {

        "education": "Undergraduate",
        "category": "OBC",
        "income": 200000,
        "state": "Karnataka",
        "gender": "Male"

    }

    # ------------------------------------------------
    # Fetch scholarships
    # ------------------------------------------------

    response = table.scan()

    scholarships = response.get("Items", [])

    matches = []

    for s in scholarships:

        income_limit = s.get("income_limit")
        education_list = s.get("education", [])
        category_list = s.get("category", [])
        state_list = s.get("state", [])
        gender_list = s.get("gender", [])

        # Income check
        if income_limit and user_profile["income"] > income_limit:
            continue

        # Education check
        if education_list and user_profile["education"] not in education_list:
            continue

        # Category check
        if category_list and "All" not in category_list and user_profile["category"] not in category_list:
            continue

        # State check
        if state_list and "All India" not in state_list and user_profile["state"] not in state_list:
            continue

        # Gender check
        if gender_list and "All" not in gender_list and user_profile["gender"] not in gender_list:
            continue

        matches.append(s)

    # ------------------------------------------------
    # Build Telegram reply
    # ------------------------------------------------

    if not matches:

        reply = "❌ No scholarships match your eligibility."

    else:

        reply = "🎓 Scholarships You Are Eligible For:\n\n"

        for s in matches[:5]:

            name = s.get("name","N/A")
            amount_min = s.get("amount_min","")
            amount_max = s.get("amount_max","")
            deadline = s.get("deadline","Not specified")
            link = s.get("application_link","")

            reply += f"🎓 {name}\n"
            reply += f"💰 Amount: ₹{amount_min} - ₹{amount_max}\n"

            if deadline:
                reply += f"📅 Deadline: {deadline}\n"

            if link:
                reply += f"🔗 Apply: {link}\n"

            reply += "\n"

    send_message(chat_id, reply)

    return {
        "statusCode": 200,
        "body": "ok"
    }
