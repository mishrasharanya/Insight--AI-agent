import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const COLORS = ["#b8541f", "#1a1a1a", "#8a8a8a", "#c9b98a", "#3a5f4a"];

export default function ChatChart({ chart }) {
  if (!chart || !chart.data?.length) return null;
  const { type, data } = chart;

  return (
    <div className="mt-4 bg-white/50 border border-[#1a1a1a]/10 p-4" data-testid="chat-chart">
      <ResponsiveContainer width="100%" height={240}>
        {type === "line" ? (
          <LineChart data={data}>
            <XAxis dataKey="label" fontSize={11} />
            <YAxis fontSize={11} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#b8541f" strokeWidth={2} />
          </LineChart>
        ) : type === "pie" ? (
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="label" outerRadius={90} label>
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip />
          </PieChart>
        ) : (
          <BarChart data={data}>
            <XAxis dataKey="label" fontSize={11} />
            <YAxis fontSize={11} />
            <Tooltip />
            <Bar dataKey="value" fill="#b8541f" />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}