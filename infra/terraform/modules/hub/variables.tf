variable "name" {
  description = "Prefix for hub resources, e.g. ailab"
  type        = string
}

variable "location" {
  type = string
}

variable "address_space" {
  description = "Hub network; spokes are allocated from the platform range by `pts ipam`"
  type        = string
}

variable "apim_sku" {
  description = "API Management SKU; Developer for the lab, Premium for production (VNet, zones)"
  type        = string
  default     = "Developer_1"
}

variable "apim_publisher_email" {
  type = string
}

variable "aks_oidc_issuer_url" {
  description = "OIDC issuer of the shared AKS cluster that runs engagement services (workload identity)"
  type        = string
}

variable "tags" {
  type = map(string)
}
