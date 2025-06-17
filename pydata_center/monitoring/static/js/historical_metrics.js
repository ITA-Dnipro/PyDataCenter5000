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

  if (startInput && endInput && new Date(startInput) > new Date(endInput)) {
    alert("End date must be after start date.");
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

  const submitButton = document.querySelector("#filterForm button[type='submit']");
  document.getElementById('loading').style.display = 'block';
  submitButton.disabled = true;

  fetch(url)
    .then(res => res.json())
    .then(data => {
      if (!Array.isArray(data) || data.length === 0) {
        alert("No data available for the selected filters.");
        return;
      }

      const metricKeys = ['cpu', 'ram', 'disk', 'load_avg'];
      const formatter = new Intl.DateTimeFormat('en-GB', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });

      chart.data.labels = data.map(item => formatter.format(new Date(item.timestamp)));

      metricKeys.forEach((key, i) => {
        chart.data.datasets[i].data = data.map(item => item[key]);
      });

      chart.update();
    })
    .catch(err => {
      console.error('Error loading data:', err);
      alert("Failed to load data.");
    })
    .finally(() => {
      document.getElementById('loading').style.display = 'none';
      submitButton.disabled = false;
    });
});
