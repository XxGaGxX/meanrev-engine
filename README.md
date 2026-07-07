# 🧠 Mean Reversion Intraday Strategy Pipeline
The Mean Reversion Intraday Strategy Pipeline is a comprehensive trading system designed to identify and capitalize on mean reversion opportunities in the financial markets. This project provides a robust framework for backtesting and executing intraday trading strategies, leveraging a combination of technical indicators, risk management techniques, and performance metrics.

## 🚀 Features
- **Configurable Strategy**: The pipeline allows for easy configuration of strategy parameters, including asset universe, timeframes, data sources, and indicator settings.
- **Multi-Indicator Support**: The system supports a range of technical indicators, including RSI, Bollinger Bands, and ADX, which can be combined to create complex trading signals.
- **Regime Filter**: A regime filter is applied to ensure that trades are only executed in favorable market conditions, reducing the risk of false signals.
- **Risk Management**: The pipeline includes a risk management module that calculates optimal position sizes based on equity, risk percentage, and volatility.
- **Performance Metrics**: The system provides a range of performance metrics, including win rate, profit factor, Sharpe ratio, and maximum drawdown, to evaluate strategy performance.

## 🛠️ Tech Stack
- **Python**: The primary programming language used for the project.
- **Pandas**: A library for data manipulation and analysis.
- **NumPy**: A library for numerical computations.
- **Alpaca-Py**: A library for interacting with the Alpaca Markets API.
- **YAML**: A configuration file format used for storing strategy parameters.
- **Dotenv**: A library for loading environment variables.

## 📦 Installation
To install the required dependencies, run the following command:
```bash
pip install -r requirements.txt
```
Ensure that you have the necessary environment variables set, including your Alpaca API credentials.

## 💻 Usage
1. Configure the strategy parameters in the `config.yaml` file.
2. Run the `data/fetch.py` module to retrieve historical data.
3. Execute the `indicators/pipeline.py` module to compute indicators and generate trading signals.
4. Run the `signals/entry.py` and `signals/exit.py` modules to simulate trades and calculate performance metrics.

## 📂 Project Structure
```markdown
.
├── config.yaml
├── data
│   ├── fetch.py
│   └── ...
├── indicators
│   ├── pipeline.py
│   └── ...
├── signals
│   ├── entry.py
│   ├── exit.py
│   └── ...
├── risk
│   ├── sizing.py
│   └── ...
├── filters
│   ├── regime.py
│   └── ...
├── utils
│   ├── config.py
│   ├── metrics.py
│   └── ...
├── requirements.txt
└── README.md
```

## 📸 Screenshots

## 🤝 Contributing
Contributions are welcome! Please submit a pull request with your changes and a brief description of the updates.

## 📝 License
This project is licensed under the MIT License.

## 📬 Contact
For questions or feedback, please contact us at [support@example.com](mailto:support@example.com).