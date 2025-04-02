document.addEventListener("DOMContentLoaded", function () {
  // Initialize theme based on user preference
  const currentTheme = localStorage.getItem("theme") || "dark";
  document.body.className = currentTheme + "-mode";
  updateThemeToggleIcon();

  // Initialize TradingView widget
  initTradingViewWidget();

  // Initialize Gamma Exposure chart
  initGammaExposureChart();

  // Set up auto-refresh interval (every 60 seconds)
  setInterval(refreshData, 60000);

  // Add event listeners
  document
    .getElementById("theme-toggle")
    .addEventListener("click", toggleTheme);
  document
    .getElementById("expiry-select")
    .addEventListener("change", updateGammaExposureChart);
  document
    .getElementById("customer-select")
    .addEventListener("change", updateGammaExposureChart);

  // Initialize rich text editor
  initRichTextEditor();

  // Load saved notes if available
  loadSavedNotes();

  // Load market data
  loadMarketData();
});

function toggleTheme() {
  if (document.body.classList.contains("dark-mode")) {
    document.body.classList.replace("dark-mode", "light-mode");
    localStorage.setItem("theme", "light");
  } else {
    document.body.classList.replace("light-mode", "dark-mode");
    localStorage.setItem("theme", "dark");
  }

  updateThemeToggleIcon();

  // Reinitialize charts with new theme
  initTradingViewWidget();
  initGammaExposureChart();
}

function updateThemeToggleIcon() {
  const themeToggle = document.getElementById("theme-toggle");
  const isDarkMode = document.body.classList.contains("dark-mode");

  themeToggle.innerHTML = isDarkMode
    ? '<i class="fas fa-sun"></i>'
    : '<i class="fas fa-moon"></i>';
}

function refreshData() {
  // Fetch latest data for all components
  loadMarketData();
  initGammaExposureChart();
}

function loadMarketData() {
  fetch("/api/market-metrics/")
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((data) => {
      updateMarketDisplay(data);
    })
    .catch((error) => {
      console.error("Error fetching market data:", error);
    });
}

function updateMarketDisplay(data) {
  // Update price display
  const spotPriceElement = document.querySelector(".spot-value");
  if (spotPriceElement) {
    spotPriceElement.textContent = data.spot_price.toFixed(2);
  }

  // Update price change display
  const changeValueElement = document.querySelector(".change-value");
  if (changeValueElement) {
    const changeValue = data.price_change_pct.toFixed(2);
    changeValueElement.textContent = `${
      changeValue > 0 ? "+" : ""
    }${changeValue}%`;

    // Apply appropriate styling based on positive/negative change
    if (data.price_change >= 0) {
      changeValueElement.classList.remove("negative");
      changeValueElement.classList.add("positive");
    } else {
      changeValueElement.classList.remove("positive");
      changeValueElement.classList.add("negative");
    }
  }

  // Update absolute change
  const changeAbsoluteElement = document.querySelector(".change-absolute");
  if (changeAbsoluteElement) {
    changeAbsoluteElement.textContent = `${
      data.price_change > 0 ? "+" : ""
    }${data.price_change.toFixed(2)}`;
  }

  // Update timestamp display
  const timestampElement = document.querySelector(".spot-timestamp");
  if (timestampElement) {
    const date = new Date(data.timestamp);
    timestampElement.textContent = `Last updated: ${date.toLocaleTimeString()} (UTC${
      date.toString().match(/GMT([+-]\d+)/)[1]
    })`;
  }
}

function initTradingViewWidget() {
  const container = document.getElementById("tradingview-container");
  if (!container) return;

  container.innerHTML = "";

  const isDarkMode = document.body.classList.contains("dark-mode");

  new TradingView.widget({
    width: "100%",
    height: "100%",
    symbol: "SPX",
    interval: "5",
    timezone: "America/New_York",
    theme: isDarkMode ? "dark" : "light",
    style: "1",
    locale: "en",
    toolbar_bg: isDarkMode ? "#242937" : "#f0f5f1",
    enable_publishing: false,
    hide_top_toolbar: false,
    container_id: "tradingview-container",
  });
}

function initGammaExposureChart() {
  // Get the container
  const container = document.getElementById("gamma-exposure-chart");
  if (!container) return;

  // Get current expiry selection
  const expirySelect = document.getElementById("expiry-select");
  const selectedExpiry = expirySelect ? expirySelect.value : "All";

  // Show loading state
  container.innerHTML =
    '<div style="display: flex; align-items: center; justify-content: center; height: 100%;"><p>Loading data...</p></div>';

  // Fetch real data from API
  fetch(`/api/gamma-exposure/?expiry_filter=${selectedExpiry}`)
    .then((response) => {
      if (!response.ok) {
        throw new Error("Network response was not ok");
      }
      return response.json();
    })
    .then((data) => {
      // Clear container
      container.innerHTML = "";

      // Create Plotly chart with the real data
      createGammaExposurePlot(container, data, selectedExpiry);
    })
    .catch((error) => {
      console.error("Error fetching gamma exposure data:", error);

      // Show error message
      container.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: center; height: 100%;">
          <p>Error loading data. Please try again later.</p>
        </div>
      `;
    });
}

function createGammaExposurePlot(container, exposureData, expiry) {
  const isDarkMode = document.body.classList.contains("dark-mode");

  // Process data for Plotly
  let data = [];

  if (exposureData && exposureData.length > 0) {
    // Sort by strike price
    const sortedData = [...exposureData].sort(
      (a, b) => a.strike_price - b.strike_price
    );

    // Limit the number of data points to avoid overcrowding
    const filteredData = sortedData.filter((item, index, arr) => {
      // Take every nth item to get reasonable number of strikes
      const step = Math.max(1, Math.floor(arr.length / 20));
      return index % step === 0;
    });

    // Extract data
    const strikes = filteredData.map((item) => item.strike_price);
    const callValues = filteredData.map(
      (item) => item.call_gamma_exposure || 0
    );
    const putValues = filteredData.map(
      (item) => -Math.abs(item.put_gamma_exposure || 0)
    ); // Make puts negative for visualization
    const netValues = filteredData.map(
      (item) => item.total_gamma_exposure || 0
    );

    // Create call trace (positive gamma)
    data.push({
      y: strikes,
      x: callValues,
      name: "Calls (Long)",
      type: "bar",
      orientation: "h",
      marker: {
        color: "#4caf50",
      },
      hovertemplate: "Strike: %{y}<br>Gamma: %{x:.2f}<extra></extra>",
    });

    // Create put trace (negative gamma)
    data.push({
      y: strikes,
      x: putValues,
      name: "Puts (Short)",
      type: "bar",
      orientation: "h",
      marker: {
        color: "#f44336",
      },
      hovertemplate: "Strike: %{y}<br>Gamma: %{x:.2f}<extra></extra>",
    });

    // Create net gamma line
    data.push({
      y: strikes,
      x: netValues,
      name: "Net Gamma",
      type: "scatter",
      mode: "lines+markers",
      line: {
        color: "#2196f3",
        width: 3,
      },
      marker: {
        size: 8,
      },
      hovertemplate: "Strike: %{y}<br>Net Gamma: %{x:.2f}<extra></extra>",
    });
  } else {
    // Sample data if no real data is available
    const strikes = [5550, 5600, 5650, 5700, 5750];
    const callValues = strikes.map(() => Math.random() * 100 + 20);
    const putValues = strikes.map(() => -Math.random() * 100 - 20);

    data = [
      {
        y: strikes,
        x: callValues,
        name: "Calls (Sample)",
        type: "bar",
        orientation: "h",
        marker: { color: "#4caf50" },
      },
      {
        y: strikes,
        x: putValues,
        name: "Puts (Sample)",
        type: "bar",
        orientation: "h",
        marker: { color: "#f44336" },
      },
    ];
  }

  // Create layout
  const layout = {
    title: `Gamma Exposure by Strike (${expiry})`,
    barmode: "relative",
    xaxis: {
      title: "Gamma Exposure",
      zeroline: true,
      zerolinecolor: isDarkMode ? "#e0e0e0" : "#333333",
      gridcolor: isDarkMode ? "#3a4254" : "#d1e0d4",
    },
    yaxis: {
      title: "Strike Price",
      type: "category",
      autorange: true,
      gridcolor: isDarkMode ? "#3a4254" : "#d1e0d4",
    },
    plot_bgcolor: isDarkMode ? "#242937" : "#ffffff",
    paper_bgcolor: isDarkMode ? "#242937" : "#ffffff",
    font: {
      color: isDarkMode ? "#e0e0e0" : "#333333",
    },
    legend: {
      orientation: "h",
      y: 1.1,
    },
    margin: {
      l: 70,
      r: 40,
      t: 50,
      b: 50,
    },
    hovermode: "closest",
  };

  // Config for the chart
  const config = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
  };

  // Create the plot
  Plotly.newPlot(container, data, layout, config);
}

function updateGammaExposureChart() {
  initGammaExposureChart();
}

function initRichTextEditor() {
  const buttons = document.querySelectorAll(".editor-btn");
  const select = document.querySelector(".editor-select");
  const editor = document.getElementById("notes-editor");

  if (!buttons.length || !select || !editor) return;

  // Add event listeners to formatting buttons
  buttons.forEach((button) => {
    button.addEventListener("click", function () {
      const command = this.dataset.command;
      document.execCommand(command, false, null);
      editor.focus();
    });
  });

  // Add event listener to font size select
  select.addEventListener("change", function () {
    const size = this.value;
    document.execCommand("fontSize", false, size);
    editor.focus();
  });

  // Save notes when content changes
  editor.addEventListener("input", function () {
    saveNotes(this.innerHTML);
  });
}

function saveNotes(content) {
  localStorage.setItem("spxDashboardNotes", content);
}

function loadSavedNotes() {
  const savedNotes = localStorage.getItem("spxDashboardNotes");
  const editor = document.getElementById("notes-editor");

  if (editor && savedNotes) {
    editor.innerHTML = savedNotes;
  }
}
