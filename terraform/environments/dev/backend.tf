terraform {
  backend "gcs" {
    bucket = "aop-tfstate-dev"
    prefix = "aop/"
  }
}
