#!/bin/sh

#
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

#
# This script kills the background process created by the tunnel-create.sh script.
# Usage:
#   tunnel-kill.sh
# Notice: This script will kill a process that was started with parameters "ssh -fN -L" and assumes that you didn't create any other ssh tunnel with the mentioned parameters.

ps aux | grep "[s]sh -o StrictHostKeyChecking=no -fN -L" | awk '{print $2}' | xargs kill -9
