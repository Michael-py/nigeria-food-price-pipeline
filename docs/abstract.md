# Seminar Paper Abstract

## Title

**Design and Implementation of an End-to-End Data Pipeline for Real-Time Food Price Monitoring and Forecasting in Nigerian Markets**

**Student Name:** [Insert Name]  
**Matriculation Number:** [Insert Number]  
**Course Code:** MIT 8212  
**Institution:** Miva Open University  
**Date:** [Insert Date]

---

## Abstract (198 words)

Food price volatility remains one of Nigeria's most pressing economic challenges, with food inflation exceeding 40% year-on-year in early 2025 and continuing to impact over 130 million citizens. Despite the availability of disparate food price data from the National Bureau of Statistics, World Food Programme, and World Bank, no integrated, automated platform exists to consolidate these sources, ensure data quality, and deliver actionable forecasts to policymakers, traders, and consumers. This study addresses this gap through the design and implementation of an end-to-end data engineering and machine learning pipeline for real-time food price monitoring and forecasting across Nigerian commodity markets. The system orchestrates multiple open-source tools — Apache Airflow for workflow orchestration, dbt for data transformation, Great Expectations for data quality validation, XGBoost for price forecasting, MLflow for experiment tracking, and FastAPI for model serving — all containerized with Docker for reproducible deployment. Evaluation against historical price data demonstrates that the XGBoost model achieves [X]% MAPE improvement over ARIMA baselines for 7-day forecasts across key staples including rice, maize, and garri. The platform is released as open-source software, providing a replicable blueprint for food price intelligence systems in data-constrained environments across Sub-Saharan Africa.

---

## Keywords

Data Engineering, Machine Learning, Food Price Forecasting, Nigeria, Apache Airflow, XGBoost, Data Pipeline, Open Source, Food Security

---

## Research Question

**How can an automated, open-source data pipeline integrating multiple public data sources and machine learning forecasting improve the timeliness and accessibility of food price intelligence for Nigerian market stakeholders?**

## Sub-Questions

1. What are the current gaps in food price data availability, quality, and accessibility in Nigeria?
2. How can disparate food price data sources be consolidated into a unified, quality-assured analytical layer using modern data engineering tools?
3. To what extent can ensemble machine learning models (XGBoost) outperform traditional statistical methods (ARIMA) in forecasting Nigerian food prices?
4. What system architecture best supports reproducible, scalable food price monitoring in data-constrained environments?
