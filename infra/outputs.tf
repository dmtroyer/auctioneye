output "lambda_function_name" {
  description = "Name of the watcher Lambda function."
  value       = aws_lambda_function.watcher.function_name
}

output "lambda_function_arn" {
  description = "ARN of the watcher Lambda function."
  value       = aws_lambda_function.watcher.arn
}

output "dynamodb_table_name" {
  description = "Name of the seen-items DynamoDB table."
  value       = aws_dynamodb_table.seen_items.name
}

output "log_group_name" {
  description = "CloudWatch log group for the Lambda."
  value       = aws_cloudwatch_log_group.lambda.name
}

output "schedule_name" {
  description = "EventBridge Scheduler schedule name."
  value       = aws_scheduler_schedule.watcher.name
}
