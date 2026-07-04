resource "aws_scheduler_schedule" "watcher" {
  name        = "${local.name}-watcher"
  description = "Runs the ${local.name} auction watcher on a schedule."

  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = var.schedule_timezone

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.watcher.arn
    role_arn = aws_iam_role.scheduler.arn
  }
}
