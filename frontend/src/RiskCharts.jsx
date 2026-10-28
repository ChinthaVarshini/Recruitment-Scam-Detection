import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

function RiskCharts({ kind, riskChartData, scoreBreakdownData, score, indicatorChartData }) {
  if (kind === "indicators") {
    return (
      <div className="chart-card indicator-chart">
        <ResponsiveContainer width="100%" height={230}>
          <BarChart
            data={indicatorChartData}
            margin={{ top: 10, right: 10, left: -20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 9 }} />
            <YAxis allowDecimals={false} tick={{ fontSize: 9 }} />
            <Tooltip />
            <Legend />
            <Bar
              dataKey="count"
              name="Detected Indicators"
              fill="#4a9678"
              radius={[5, 5, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  return (
    <div className="charts-grid">
      <div className="chart-card">
        <div className="chart-title">Overall Risk Score</div>
        <ResponsiveContainer width="100%" height={230}>
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="65%"
            outerRadius="95%"
            startAngle={90}
            endAngle={-270}
            barSize={18}
            data={riskChartData}
          >
            <RadialBar background dataKey="value" cornerRadius={10} />
            <text
              x="50%"
              y="48%"
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="28"
              fontWeight="800"
              fill="#24443a"
            >
              {score}%
            </text>
            <text
              x="50%"
              y="61%"
              textAnchor="middle"
              dominantBaseline="middle"
              fontSize="11"
              fill="#789087"
            >
              RISK SCORE
            </text>
          </RadialBarChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <div className="chart-title">Risk Components</div>
        <ResponsiveContainer width="100%" height={230}>
          <BarChart
            data={scoreBreakdownData}
            margin={{ top: 10, right: 10, left: -20, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 9 }} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 9 }} />
            <Tooltip />
            <Bar dataKey="score" name="Score" fill="#28765b" radius={[5, 5, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default RiskCharts;