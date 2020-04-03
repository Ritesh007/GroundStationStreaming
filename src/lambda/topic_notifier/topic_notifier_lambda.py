from __future__ import print_function

import json
import boto3
from kafka import KafkaProducer
import urllib
import ssl
import logging
import io
import os

root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)
logging.basicConfig(format='%(asctime)s %(message)s',level=logging.DEBUG)



def lambda_handler(event, context):
        
    print('Loading function')

    s3 = boto3.client('s3')
    ssm_client = boto3.client('ssm', os.environ['ssm_region'])
    BOOTSTRAP_SERVERS = ssm_client.get_parameter(Name=os.environ['bootstrap_servers_ssm_key'])['Parameter']['Value'].split(" ")
    TOPIC = ssm_client.get_parameter(Name=os.environ['topic_ssm_key'])['Parameter']['Value']

    producer = KafkaProducer(
       bootstrap_servers=BOOTSTRAP_SERVERS,
       value_serializer=lambda m: json.dumps(m).encode('ascii'),
       retry_backoff_ms=500,
       request_timeout_ms=20000,
    )


    print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key'].encode('utf8')

    try:
        print("New object in bucket {}, with key {}".format(bucket, key))
        future = producer.send(TOPIC,"New object in bucket {}, with key {}".format(bucket, key))
        record_metadata = future.get(timeout=10)
        print("sent event to Kafka! topic {} partition {} offset {}".format(record_metadata.topic, record_metadata.partition, record_metadata.offset))

    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. '.format(key, bucket))
        raise e


if __name__ == '__main__':
  data = '{\
    "Records": [\
      {\
        "eventVersion": "2.0",\
        "eventSource": "aws:s3",\
        "awsRegion": "us-east-2",\
        "eventTime": "1970-01-01T00:00:00.000Z",\
        "eventName": "ObjectCreated:Put",\
        "userIdentity": {\
          "principalId": "EXAMPLE"\
        },\
        "requestParameters": {\
          "sourceIPAddress": "127.0.0.1"\
        },\
        "responseElements": {\
          "x-amz-request-id": "EXAMPLE123456789",\
          "x-amz-id-2": "EXAMPLE123/5678abcdefghijklambdaisawesome/mnopqrstuvwxyzABCDEFGH"\
        },\
        "s3": {\
          "s3SchemaVersion": "1.0",\
          "configurationId": "testConfigRule",\
          "bucket": {\
            "name": "example-bucket",\
            "ownerIdentity": {\
              "principalId": "EXAMPLE"\
            },\
            "arn": "arn:aws:s3:::example-bucket"\
          },\
          "object": {\
            "key": "test/key",\
            "size": 1024,\
            "eTag": "0123456789abcdef0123456789abcdef",\
            "sequencer": "0A1B2C3D4E5F678901"\
          }\
        }\
      }\
    ]\
  }'
  event = json.loads(data)
  lambda_handler(event, None)