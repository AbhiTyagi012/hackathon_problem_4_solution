import type { Condition } from "../api/types";

export function summarizeCondition(c: Condition): string {
  if (c.all) return "(" + c.all.map(summarizeCondition).join(" AND ") + ")";
  if (c.any) return "(" + c.any.map(summarizeCondition).join(" OR ") + ")";
  if (c.not) return `NOT ${summarizeCondition(c.not)}`;
  return `${c.field} ${c.operator} ${JSON.stringify(c.value)}`;
}

export function ConditionTree({ condition }: { condition: Condition }) {
  return <code style={{ fontSize: 12.5 }}>{summarizeCondition(condition)}</code>;
}
