#!/usr/bin/env bash
set -euo pipefail

REGION="spaincentral"
STATE_RG="rg-ctf-tfstate"
SUB_ID="$(az account show --query id -o tsv)"
STORAGE_NAME="ctfstate$(printf '%s' "$SUB_ID" | sha256sum | cut -c1-12)"

echo "Subscription: $(az account show --query name -o tsv)"
echo "Storage account: $STORAGE_NAME"

read -rp 'Create Terraform state storage? Type YES: ' confirm
[[ "$confirm" == "YES" ]] || exit 1

az group create \
  --name "$STATE_RG" \
  --location "$REGION" \
  -o none

az storage account create \
  --name "$STORAGE_NAME" \
  --resource-group "$STATE_RG" \
  --location "$REGION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --https-only true \
  --allow-blob-public-access false \
  --allow-shared-key-access false \
  -o none

az storage container-rm create \
  --resource-group "$STATE_RG" \
  --storage-account "$STORAGE_NAME" \
  --name tfstate \
  --public-access off \
  -o none

echo "Backend created successfully"
echo "Resource group: $STATE_RG"
echo "Storage account: $STORAGE_NAME"
echo "Container: tfstate"
echo "Next: assign Storage Blob Data Contributor to your Azure user."
