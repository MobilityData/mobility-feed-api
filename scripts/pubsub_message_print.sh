#!/bin/bash

#
#  MobilityData 2023
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
#


# This function uses the Pub/Sub emulator to create a subscription and count the number of messages in a topic.
# If you are debbuging locally with a consumer of the topic, 
# you should not be running this script if the consumer shares the same subscription name.
# As this script and any consumer sharing the same subscription will be competing for the messages in the topic.
# If consumers have different subscription names, they will each receive a copy of the messages.
#
# Requires the jq command-line JSON processor: https://stedolan.github.io/jq/
# 
# Usage: ./pubsub_message_print.sh <TOPIC_NAME>



export PUBSUB_EMULATOR_HOST="localhost:8043"


PROJECT="test-project"
SUBSCRIPTION_NAME="my-subscription"


TOPIC_NAME="$1"


if [ -z "$TOPIC_NAME" ]; then
  echo "Error: No topic name provided."
  echo "Usage: ./pubsub_message_count.sh <TOPIC_NAME>"
  exit 1
fi


create_subscription() {
  echo "Creating subscription: $SUBSCRIPTION_NAME"
  SUBSCRIPTION_URL="http://$PUBSUB_EMULATOR_HOST/v1/projects/$PROJECT/subscriptions/$SUBSCRIPTION_NAME"
  TOPIC_URL="projects/$PROJECT/topics/$TOPIC_NAME"

  BODY=$(cat <<EOF
{
  "topic": "$TOPIC_URL"
}
EOF
)

  curl -X PUT "$SUBSCRIPTION_URL" -H "Content-Type: application/json" -d "$BODY"
  
  echo ""
}

pull_messages() {
  echo "Pulling messages from subscription: $SUBSCRIPTION_NAME"
  TOTAL_MESSAGES=0

  while :; do
    PULL_URL="http://$PUBSUB_EMULATOR_HOST/v1/projects/$PROJECT/subscriptions/$SUBSCRIPTION_NAME:pull"

    PULL_BODY=$(cat <<EOF
{
  "maxMessages": 10
}
EOF
)

    RESPONSE=$(curl -s -X POST "$PULL_URL" -H "Content-Type: application/json" -d "$PULL_BODY")

    BATCH_COUNT=$(echo "$RESPONSE" | jq '.receivedMessages | length')

    if [[ "$BATCH_COUNT" -eq 0 ]]; then
      break
    fi

    TOTAL_MESSAGES=$((TOTAL_MESSAGES + BATCH_COUNT))

    # Display each message's body (base64 decoded) and the message ID
    echo "$RESPONSE" | jq -r '.receivedMessages[] | "\(.message.messageId): \(.message.data)"' | while read -r line; do
      MESSAGE_ID=$(echo "$line" | cut -d':' -f1)
      ENCODED_DATA=$(echo "$line" | cut -d':' -f2 | tr -d ' ')
      DECODED_DATA=$(echo "$ENCODED_DATA" | base64 --decode)
      echo "Message ID: $MESSAGE_ID"
      echo "Message Body: $DECODED_DATA"
      echo "----"
    done

    # Acknowledge the messages to remove them from the subscription
    ACK_IDS=$(echo "$RESPONSE" | jq -r '.receivedMessages[].ackId' | tr '\n' ',' | sed 's/,$//')

    if [ -n "$ACK_IDS" ]; then
      ACK_URL="http://$PUBSUB_EMULATOR_HOST/v1/projects/$PROJECT/subscriptions/$SUBSCRIPTION_NAME:acknowledge"
      ACK_BODY=$(cat <<EOF
{
  "ackIds": ["$ACK_IDS"]
}
EOF
)

      curl -s -X POST "$ACK_URL" -H "Content-Type: application/json" -d "$ACK_BODY"
    fi
  done

  echo "Total messages pulled: $TOTAL_MESSAGES"
}


main() {
  create_subscription
  pull_messages
}

main
