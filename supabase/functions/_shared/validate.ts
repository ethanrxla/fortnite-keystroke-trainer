// Port of companion/keystroke_lab/attempt_schema.py: the same keyword subset, the same messages.
// A record the companion accepts is accepted here; anything else is rejected before it touches the database.
// deno-lint-ignore-file no-explicit-any
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const TYPES: Record<string, (v: any) => boolean> = {
  object: (v) => v !== null && typeof v === "object" && !Array.isArray(v),
  array: (v) => Array.isArray(v),
  string: (v) => typeof v === "string",
  integer: (v) => typeof v === "number" && Number.isInteger(v),
  number: (v) => typeof v === "number" && Number.isFinite(v),
  boolean: (v) => typeof v === "boolean",
  null: (v) => v === null,
};

export function keySummaryErrors(value:any):string[]{
  if(value==null)return [];
  if(!TYPES.object(value)||Object.keys(value).some(k=>k!=="verdicts")||!TYPES.object(value.verdicts))
    return ["key_summary: anonymous verdict totals only"];
  const allowed=new Set(["ok","order","stray","double","unmapped","repeat","release","habit"]);
  return Object.entries(value.verdicts).some(([k,v])=>!allowed.has(k)||!Number.isSafeInteger(v)||Number(v)<0||Number(v)>1000000)
    ?["key_summary: invalid verdict or count"]:[];
}

export function errors(value: any, schema: any, path = "$"): string[] {
  const out: string[] = [];
  if (schema.type !== undefined) {
    const kinds: string[] = Array.isArray(schema.type) ? schema.type : [schema.type];
    if (!kinds.some((k) => TYPES[k](value))) return [`${path}: expected ${kinds.join("/")}`];
  }
  if ("const" in schema && value !== schema.const) out.push(`${path}: must be ${JSON.stringify(schema.const)}`);
  if (schema.enum && !schema.enum.includes(value)) out.push(`${path}: ${JSON.stringify(value)} not allowed`);
  if (typeof value === "string") {
    if (schema.maxLength !== undefined && value.length > schema.maxLength) out.push(`${path}: longer than ${schema.maxLength}`);
    if (schema.format === "uuid" && !UUID.test(value)) out.push(`${path}: not a lowercase uuid`);
  }
  if (TYPES.number(value)) {
    if (schema.minimum !== undefined && value < schema.minimum) out.push(`${path}: below ${schema.minimum}`);
    if (schema.maximum !== undefined && value > schema.maximum) out.push(`${path}: above ${schema.maximum}`);
  }
  if (Array.isArray(value)) {
    if (schema.minItems !== undefined && value.length < schema.minItems) out.push(`${path}: fewer than ${schema.minItems} items`);
    if (schema.maxItems !== undefined && value.length > schema.maxItems) out.push(`${path}: more than ${schema.maxItems} items`);
    if (schema.items) value.forEach((item, i) => out.push(...errors(item, schema.items, `${path}[${i}]`)));
  }
  if (TYPES.object(value)) {
    const props = schema.properties ?? {};
    for (const key of schema.required ?? []) if (!(key in value)) out.push(`${path}: missing ${key}`);
    if (schema.additionalProperties === false) {
      for (const key of Object.keys(value)) if (!(key in props)) out.push(`${path}: unexpected field ${key}`);
    }
    for (const [key, sub] of Object.entries(props)) if (key in value) out.push(...errors(value[key], sub, `${path}.${key}`));
  }
  if (path === "$" && TYPES.object(value) && value.schema === "edit_attempt.v2") {
    const opened=value.t_edit_open, closed=value.t_close;
    if(TYPES.number(opened) && TYPES.number(closed)){
      if(closed<opened)out.push("$: close precedes open");
      for(const key of ["t_first_select","t_confirm","t_reset"])
        if(TYPES.number(value[key]) && !(opened<=value[key] && value[key]<=closed+.15))out.push("$."+key+": outside attempt");
    }
    const bound=value.piece==="wall"?9:["floor","cone","ramp"].includes(value.piece)?4:0;
    const trace=Array.isArray(value.selection_trace)?value.selection_trace:[];
    const selections=[value.final_tiles??[],...trace.filter(TYPES.object).map((s:any)=>s.tiles??[])];
    if(selections.some(s=>Array.isArray(s) && (new Set(s).size!==s.length || s.some(t=>!Number.isInteger(t)||t<0||t>=bound))))
      out.push("$: selection outside piece topology or repeated");
    if(value.outcome==="result_verified" && !(value.result_confirmed===true && ["authored","reviewed"].includes(value.result_evidence)))
      out.push("$: verified outcome needs result evidence");
  }
  return out;
}
