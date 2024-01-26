# Set up new GCP environment

`All roads lead to Rome!` This quote is a reminder that there are multiple ways to get to the same final state.
Take the following steps as a guidance and adapt them to your own local and organizational requirements.
For more information regarding Google Cloud Platform and terraform go to the [Official GCP Site](https://cloud.google.com/) and [Terraform Official Site](https://www.terraform.io/).

## Initial project and remote state set up

- Create GCP project

```shell
gcloud projects create PROJECT_ID --name="Mobility Feeds API"
```

- Assign a billing account to the project
- Create a Firebase project to host the UI
- Create Oauth credentials and to be used as part of the terraform parameters
- Create SSL certificates for the Load Balancer
- Enable and configure Identity Platform
- Login to gcloud cli using,

```shell
gcloud auth application-default login
```

- Point local project environment variable to the newly created project

```shell
gcloud config set project PROJECT_ID
```

- Create Cloud Storage Bucket. Example, mobility-feeds-terraform-init-<environment>.
- Open the terminal in the folder `<project_dir>/infra/terraform-init`
- Create a terraform backend file using the template `backend.conf.rename_me` with name backend-<environment>.conf and populate the file with valid values.
- Execute,

```shell
terraform init -backend-config=backend-<environment>.conf
```

- Create a terraform variables file using the template `vars.tfvars.rename_me` with name vars-<env>.tfvars and populate the file with valid values.
- Execute and review the terraform plan,

```shell
  terraform plan -var-file=vars-<environment>.tfvars
```

- Once you had reviewed the plan, execute the terraform apply command to commit the changes to the GCP environment using,
- To be able to execute the apply command on the terraform-init project you need Project IAM Admin role

```shell
terraform apply -var-file=vars-<environment>.tfvars
```

- Troubleshooting
  - Make sure you have the right permissions.
  - `There is a delay due to configuration propagation on newly GCP enabled services`. In this case wait for the change to be propagated and execute the terraform apply command again.
  - If you had a previous GCP environment set up in your local folders, remove `.terraform` folder and `terraform.state*` files locally before running `terraform init` command.

### Adding new GCP service to the stack

The initial project set up is required while setting up a GCP environment also when `a new GCP service` is added to the stack.
When a new service is added to the stack the service account used to deploy the infrastructure needs to have the required permissions.
In this case,

- Add/modify roles and policies as necessary to the deployer's servie account in the `infra/terraform-init/main.tf`
- From `infra/terraform-init/` execute,

```shell
terraform apply -var-file=vars-<environment>.tfvars
```

- Now you are in position to execute the main terraform script from `infra` folder.

## Deploy Feeds API

- Open the terminal in the folder `<project_dir>/infra`
- Create a terraform backend file using the template `backend.conf.rename_me` with name backend-<environment>.conf and populate the file with valid values.
- Execute,

```shell
terraform init -backend-config=backend-<environment>.conf
```

- One-time artifact set up. Set up the GCP artifact registry before-hand to be able to publish docker images.

```shell
terraform apply -var-file=vars-<environment>.tfvars -target=module.artifact-registry
```

- Remember that: `There is a delay due to configuration propagation on newly GCP enabled services.`. You might get 403 responses while GCP is propagating the new configuration.
- You need at least one docker image published to be able to deploy the cloud run service. Execute the following script,

```shell
<project_dir>/scripts/docker-build-push.sh -project_id mobility-feeds-<environment> -service feed-api -repo_name feeds-<environment> -region northamerica-northeast1 -version <version_number>
```

- Set the version number on the `infra/vars-<environment>.tfvars` file.
- Execute apply from infra folder

```shell
terraform apply -var-file=vars-<environment>.tfvars
```

- Enjoy Coding!
