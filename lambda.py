import json
import boto3
from botocore.exceptions import ClientError
import urllib3
import email
import re

def lambda_handler(event, context):
    rc = processIncoming(event)
    return {
        'statusCode': 200,
        'body': json.dumps(rc)
    }

def sendEmail(email, text):
    SENDER = "MG Weather <weather@noreply.moegirl.live>"
    RECIPIENT = email
    AWS_REGION = "us-east-2"
    SUBJECT = "Weather Update"
    BODY_TEXT = (text)
    CHARSET = "ISO-8859-1"
    client = boto3.client('ses',region_name=AWS_REGION)

    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': CHARSET,
                        'Data': BODY_TEXT,
                    },
                },
                'Subject': {
                    'Charset': CHARSET,
                    'Data': SUBJECT,
                },
            },
            Source=SENDER,
        )
        rc = ""
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
        rc = e.response['Error']['Message']
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])
        rc = response['MessageId']
    return rc

def forcast3day(lat = "45.424721", lon = "-75.695000"):

    #dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    
    headers = {'Accept': 'application/json'}
    
    base_url = "https://api.open-meteo.com/v1/forecast?latitude=45.424721&longitude=-75.695000&current=temperature_2m,relative_humidity_2m,pressure_msl&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_dominant&timezone=auto&forecast_days=3"
    
    
    url = base_url.replace("45.424721", lat)
    url = base_url.replace("-75.695000", lon)
    
    r = urllib3.PoolManager().request('GET', url, headers=headers)
    
    data = json.loads(r.data)
    
    time = f"{data['current']['time']}{data['timezone_abbreviation']}"
    temperature = f"{data['current']['temperature_2m']}{data['current_units']['temperature_2m']}"
    humidity = f"{data['current']['relative_humidity_2m']}{data['current_units']['relative_humidity_2m']}RH"
    pressure = f"Baro:{data['current']['pressure_msl']}{data['current_units']['pressure_msl']}"
    
    #print(f"{time} {temperature} {humidity} {pressure}")

    output = []
    output.append(f"{lat.split('.')[0]}.{lat.split('.')[1][:2]},{lon.split('.')[0]}.{lon.split('.')[1][:2]}")
    
    for i in range(0, 3):
        item = {}
        for key in data["daily"]:
            item[key] = data["daily"][key][i]
        date = "-".join(f"{item['time']}".split("-")[1:])
        weather = f"{item['weather_code']}"
        temperature = f"{item['temperature_2m_min']}~{item['temperature_2m_max']}{data['daily_units']['temperature_2m_max']}"
        pop = f"{item['precipitation_probability_max']}{data['daily_units']['precipitation_probability_max']}"
        precipitation = f"{item['precipitation_sum']}{data['daily_units']['precipitation_sum']}"
        #wind = f"{item['wind_speed_10m_max']}{data['daily_units']['wind_speed_10m_max']}@{item['wind_direction_10m_dominant']}{data['daily_units']['wind_direction_10m_dominant']}"
        #https://gist.github.com/RobertSudwarts/acf8df23a16afdb5837f
        wind = f"{item['wind_speed_10m_max']}{data['daily_units']['wind_speed_10m_max']} {dirs[round(item['wind_direction_10m_dominant'] / (360. / len(dirs))) % len(dirs)]}"
        #print(f"{date} {weather} {temperature} {precipitation} {wind}")
        output.append(f"{date} {weather} {temperature} {precipitation} {wind}")

    #https://www.wpc.ncep.noaa.gov/html/contract.html
    #https://www.nodc.noaa.gov/archive/arc0021/0002199/1.1/data/0-data/HTML/WMO-CODE/WMO4677.HTM

    if len("\n".join(output)) < 140:
        return "\n".join(output)
    else:
        return "\n".join(output[1:])


def getEmailBody(text):
    #https://stackoverflow.com/questions/17874360/python-how-to-parse-the-body-from-a-raw-email-given-that-raw-email-does-not
    b = email.message_from_string(text)
    body = text.encode("utf-8")

    if b.is_multipart():
        for part in b.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get('Content-Disposition'))

            # skip any text/plain (txt) attachments
            if ctype == 'text/plain' and 'attachment' not in cdispo:
                body = part.get_payload(decode=True)  # decode
                break
    # not multipart - i.e. plain text, no attachments, keeping fingers crossed
    else:
        body = b.get_payload(decode=True)

    return body.decode("utf-8")
    
def processIncoming(event):
    mail_obj = json.loads(event['Records'][0]['Sns']['Message'])
    email_addr = mail_obj['mail']['source']
    content = getEmailBody(mail_obj['content'])
    lat = re.search(r'(-?\d+.\d+),(-?\d+.\d+)', content)[1]
    lon = re.search(r'(-?\d+.\d+),(-?\d+.\d+)', content)[2]
    
    rc = ""
    
    if email_addr.endswith("@textmyspotx.com"):
        weather_data = forcast3day(lat, lon)
        rc = sendEmail(email_addr, weather_data)
    else:
        rc = "Not from spotx"
    
    return rc
