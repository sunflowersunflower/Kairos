import boto3
import os
import json
import time
import urllib3
http = urllib3.PoolManager()

TRANSCRIPTS_OUTPUT_PREFIX = 'transcripts/'

region = os.environ.get('AWS_REGION')
recording_bucket = os.environ.get('RecordingStorageBucketName')

s3 = boto3.client('s3', region_name=region)
bedrock = boto3.client('bedrock-runtime', region_name=region)
transcribe = boto3.client('transcribe', region_name=region)
def lambda_handler(event, context):
    print(event)
    for record in event['Records']:
        key_name = record['s3']['object']['key']
        print(key_name)
        if key_name.startswith(TRANSCRIPTS_OUTPUT_PREFIX):
            return
        uri = f"s3://{recording_bucket}/{key_name}"
        print(f"processing {uri}")
        transcript = extract_transcript(uri)
        response_body = invoke_model(transcript)
        send_slack_notification(response_body['content'][0]['text'])

def extract_transcript(uri):
    job_name = f"transcription_{int(time.time())}"
    media_uri = uri
    media_format = uri.split('.')[-1]

    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': media_uri},
        MediaFormat=media_format,
        LanguageCode='en-US',
        OutputBucketName=recording_bucket,
        OutputKey=TRANSCRIPTS_OUTPUT_PREFIX,
        Settings={'ShowSpeakerLabels': True, 'MaxSpeakerLabels': 2}
    )

    while True:
        print("waiting for the job to complete ....")
        time.sleep(60)
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)['TranscriptionJob']['TranscriptionJobStatus']
        if status in ['COMPLETED', 'FAILED']:
            break

    transcript_file_key = f"{TRANSCRIPTS_OUTPUT_PREFIX}{job_name}.json"
    result = s3.get_object(Bucket=recording_bucket, Key=transcript_file_key)
    transcript = json.loads(result["Body"].read().decode("utf-8"))
    return transcript['results']['transcripts'][0]['transcript']

def invoke_model(transcript):
    print("generating summary ...")
    system_prompt = "Create a summary that captures the essential information, focusing on key takeaways and action items assigned to specific individuals or departments during the meeting. Use clear and professional language, and organize the summary in a logical manner using appropriate formatting such as headings, subheadings, and bullet points. Ensure that the summary is easy to understand and provides a comprehensive but succinct overview of the meeting's content, with a particular focus on clearly indicating who is responsible for each action item."
    user_message =  {"role": "user", "content": transcript}
    messages = [user_message]
    body=json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": messages
        }
    )
    response = bedrock.invoke_model(body=body, modelId="anthropic.claude-3-sonnet-20240229-v1:0")
    response_body = json.loads(response.get('body').read())

    return response_body

def send_slack_notification(content):
    print("sending to slack channel ...")
    url = "https://hooks.slack.com/workflows/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"
    msg = {
        "text": "this is to slack channel",
        "content": content
    }
    headers = {"Content-type": "application/json"}

    encoded_msg = json.dumps(msg).encode('utf-8')
    resp = http.request('POST',url, body=encoded_msg, headers=headers)
    print({
        "message": content,
        "status_code": resp.status,
        "response": resp.data
    })