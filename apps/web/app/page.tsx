import { regulatoryQuerySchema } from "@finreg/core";

const fields = Object.entries(regulatoryQuerySchema.properties).map(
  ([name, details]) => ({
    name,
    type: details.type
  })
);

export default function Home() {
  return (
    <main
      style={{
        fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif",
        padding: "64px 24px",
        maxWidth: 960,
        margin: "0 auto",
        display: "flex",
        flexDirection: "column",
        gap: 24
      }}
    >
      <header style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <span style={{ fontSize: 14, textTransform: "uppercase", letterSpacing: 2 }}>
          EU Fintech Regulatory Assistant
        </span>
        <h1 style={{ fontSize: 40, margin: 0 }}>
          Graph-native regulatory intelligence for compliance teams
        </h1>
        <p style={{ margin: 0, maxWidth: 640, lineHeight: 1.6 }}>
          Query EU regulatory obligations, map cross-border dependencies, and track
          supervisory expectations across jurisdictions.
        </p>
      </header>
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 16
        }}
      >
        {fields.map((field) => (
          <div
            key={field.name}
            style={{
              border: "1px solid #d6d6d6",
              borderRadius: 12,
              padding: 16,
              display: "flex",
              flexDirection: "column",
              gap: 8
            }}
          >
            <strong style={{ fontSize: 16 }}>{field.name}</strong>
            <span style={{ fontSize: 12, opacity: 0.7 }}>{field.type}</span>
          </div>
        ))}
      </section>
      <footer style={{ fontSize: 12, opacity: 0.7 }}>
        Schema source: {regulatoryQuerySchema.title}
      </footer>
    </main>
  );
}
