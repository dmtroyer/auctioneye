resource "aws_dynamodb_table" "seen_items" {
  name         = "${local.name}-seen-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Project = local.name
  }
}
