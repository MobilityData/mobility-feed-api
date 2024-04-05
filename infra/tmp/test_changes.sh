echo "Running test_changes.sh"
echo "[INFO] Building Python functions..."
../../scripts/function-python-build.sh --function_name validation_report_processor

echo "[INFO] Running Terraform init"
terraform init

echo "[INFO] Running Terraform plan"
terraform plan -var-file=vars.tfvars -out=tf.plan

echo "[INFO] Running Terraform apply"
terraform apply "tf.plan"

echo "[INFO] Script completed successfully!"
exit 0