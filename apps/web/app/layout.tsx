export const metadata = {
  title: "EU Fintech Regulatory Assistant",
  description: "Regulatory intelligence for EU fintech teams"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
