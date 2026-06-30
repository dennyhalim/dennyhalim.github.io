require_relative 'Plugin'
require 'date'

# Show days remaining until (or since) one or more target dates.
# Recomputed every build, so combine with the daily scheduled rebuild
# in `.github/workflows/build.yml` to keep counters fresh.
#
# Hash-style — labels become keys:
#   plugins:
#     - CountdownPlugin:
#         new_year: 2027-01-01
#         launched: 2024-06-15
#
# Output (Hash<String, Hash>):
#   {
#     "new_year" => { "days" => 235, "target" => "2027-01-01", "passed" => false },
#     "launched" => { "days" => 692, "target" => "2024-06-15", "passed" => true }
#   }
#
# Use in Liquid:
#   {% if vars.CountdownPlugin.new_year.passed %}
#     🎉 New year is here!
#   {% else %}
#     ⏳ {{ vars.CountdownPlugin.new_year.days }} days until New Year
#   {% endif %}
class CountdownPlugin < Plugin
  def execute
    today = Date.today
    params.each_with_object({}) do |(label, target), out|
      out[label.to_s] = compute(today, target)
    end
  end

  private

  def compute(today, target)
    target_date = parse_date(target)
    return { 'days' => 0, 'target' => target.to_s, 'passed' => false } unless target_date

    delta = (target_date - today).to_i
    {
      'days' => delta.abs,
      'target' => target_date.strftime('%Y-%m-%d'),
      'passed' => delta < 0
    }
  end

  def parse_date(value)
    case value
    when Date then value
    when Time then value.to_date
    when String then Date.parse(value)
    end
  rescue ArgumentError
    log("could not parse date: #{value.inspect}")
    nil
  end
end
