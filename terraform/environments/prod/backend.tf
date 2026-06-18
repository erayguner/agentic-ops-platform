terraform {
  backend "gcs" {
    bucket = "aop-tfstate-prod"
    prefix = "aop/"
  }
}
