const ctx = document.getElementById('metricsChart').getContext('2d');

const chart = new Chart(ctx, {
  type: 'line',
  data: {
    labels: [],
    datasets: [
      {
        label: 'CPU Usage (%)',
        data: [],
        borderColor: 'rgb(255, 99, 132)',
        borderWidth: 2,
        fill: false,
        tension: 0.1
      },
      {
        label: 'RAM Usage (%)',
        data: [],
        borderColor: 'rgb(54, 162, 235)',
        borderWidth: 2,
        fill: false,
        tension: 0.1
      },
      {
        label: 'Disk Usage (%)',
        data: [],
        borderColor: 'rgb(75, 192, 192)',
        borderWidth: 2,
        fill: false,
        tension: 0.1
      },
      {
        label: 'Load Average',
        data: [],
        borderColor: 'rgb(153, 102, 255)',
        borderWidth: 2,
        fill: false,
        tension: 0.1
      }
    ]
  },
  options: {
    responsive: true,
    scales: {
      y: {
        beginAtZero: true
      }
    }
  }
});

document.getElementById('filterForm').addEventListener('submit', function(e) {
  e.preventDefault();

  const hostname = document.getElementById('hostnameSelect').value;
  const startInput = document.getElementById('startDate').value;
  const endInput = document.getElementById('endDate').value;

  if (!hostname) {
    alert("Please select a hostname.");
    return;
  }

  const params = new URLSearchParams();
  params.append('hostname', hostname);

  if (startInput) {
    try {
      const start = new Date(startInput).toISOString();
      params.append('start', start);
    } catch (e) {
      alert("Invalid start date.");
      return;
    }
  }

  if (endInput) {
    try {
      const end = new Date(endInput).toISOString();
      params.append('end', end);
    } catch (e) {
      alert("Invalid end date.");
      return;
    }
  }

  const url = `/api/v1/metrics/history/?${params.toString()}`;

  fetch(url)
    .then(res => res.json())
    .then(data => {
      const labels = data.map(item => new Date(item.timestamp).toLocaleString());
      const cpuData = data.map(item => item.cpu);
      const ramData = data.map(item => item.ram);
      const diskData = data.map(item => item.disk);
      const loadAvgData = data.map(item => item.load_avg);

      chart.data.labels = labels;
      chart.data.datasets[0].data = cpuData;
      chart.data.datasets[1].data = ramData;
      chart.data.datasets[2].data = diskData;
      chart.data.datasets[3].data = loadAvgData;
      chart.update();
    })
    .catch(err => {
      console.error('Error loading data:', err);
    });
});
