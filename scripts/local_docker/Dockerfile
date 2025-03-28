# This docker is used to test locally scripts that are executed in the CI.
# How to run the container and have shell access:
# docker build -t ubuntu-local-python311 .
# docker run -it ubuntu-local-python311
 
FROM ubuntu:latest

# Install prerequisites and add deadsnakes PPA for newer Python versions
RUN apt-get update && apt-get install -y software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update

# Install Python 3.11 and Git
RUN apt-get install -y python3.11 python3.11-dev python3-pip git

# Optional: update alternatives to make python3.11 the default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Set working directory
WORKDIR /app

CMD ["bash"]
