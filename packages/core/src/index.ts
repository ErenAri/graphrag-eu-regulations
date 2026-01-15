import schema from "./schemas/regulatory-query.schema.json";

export type RegulatoryQuery = {
  user_id: string;
  jurisdiction: "EU";
  question: string;
  context?: string;
};

export const regulatoryQuerySchema = schema as {
  title: string;
  properties: Record<string, { type: string; const?: string }>;
  required: string[];
};
