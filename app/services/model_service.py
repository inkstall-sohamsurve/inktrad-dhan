from typing import Any, Dict, List, Optional

import logging
import math

import numpy as np
import torch
from scripts.nse_security_ids import resolve_security_id
logger = logging.getLogger(__name__)


class StackedLSTMModel(torch.nn.Module):
    def __init__(self, input_size: int, output_size: int) -> None:
        super().__init__()
        self.lstm1 = torch.nn.LSTM(input_size, 64, batch_first=True)
        self.bn1 = torch.nn.BatchNorm1d(64)
        self.drop1 = torch.nn.Dropout(0.2)
        self.lstm2 = torch.nn.LSTM(64, 32, batch_first=True)
        self.bn2 = torch.nn.BatchNorm1d(32)
        self.drop2 = torch.nn.Dropout(0.2)
        self.lstm3 = torch.nn.LSTM(32, 16, batch_first=True)
        self.bn3 = torch.nn.BatchNorm1d(16)
        self.fc = torch.nn.Linear(16, output_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        out, _ = self.lstm1(x)
        out = self.drop1(self.bn1(out.permute(0, 2, 1)).permute(0, 2, 1))
        out, _ = self.lstm2(out)
        out = self.drop2(self.bn2(out.permute(0, 2, 1)).permute(0, 2, 1))
        out, _ = self.lstm3(out)
        return self.fc(self.bn3(out[:, -1, :]))


class ModelService:
    _instance: Optional["ModelService"] = None

    def __init__(self) -> None:
        self.device = torch.device("cpu")
        self.lookback = 60
        self.prediction_features: List[str] = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "volatility_index",
            "decay",
        ]
        self.scalers: Optional[Dict[str, Any]] = None
        self.label_encoder: Any = None

        try:
            loaded = torch.load("ml/lstm_pytorch.pth", map_location=self.device)
            model: Optional[torch.nn.Module] = None
            state_dict: Optional[Dict[str, torch.Tensor]] = None

            if isinstance(loaded, torch.nn.Module):
                model = loaded
            elif isinstance(loaded, dict):
                inner = loaded.get("model")
                if isinstance(inner, torch.nn.Module):
                    model = inner
                    self.lookback = int(loaded.get("lookback", self.lookback))
                    scalers = loaded.get("scalers")
                    if isinstance(scalers, dict):
                        self.scalers = scalers
                    label_encoder = loaded.get("label_encoder")
                    if label_encoder is not None:
                        self.label_encoder = label_encoder
                    prediction_features = loaded.get("prediction_features")
                    if isinstance(prediction_features, list) and prediction_features:
                        self.prediction_features = prediction_features
                else:
                    if "state_dict" in loaded and isinstance(loaded["state_dict"], dict):
                        cand = loaded["state_dict"]
                        if all(isinstance(v, torch.Tensor) for v in cand.values()):
                            state_dict = cand
                    elif "model_state" in loaded and isinstance(loaded["model_state"], dict):
                        cand = loaded["model_state"]
                        if all(isinstance(v, torch.Tensor) for v in cand.values()):
                            state_dict = cand
                    elif loaded and all(isinstance(v, torch.Tensor) for v in loaded.values()):
                        state_dict = loaded

                    if state_dict is not None:
                        if isinstance(loaded, dict):
                            self.lookback = int(loaded.get("lookback", self.lookback))
                            scalers = loaded.get("scalers")
                            if isinstance(scalers, dict):
                                self.scalers = scalers
                            label_encoder = loaded.get("label_encoder")
                            if label_encoder is not None:
                                self.label_encoder = label_encoder
                            prediction_features = loaded.get("prediction_features")
                            if isinstance(prediction_features, list) and prediction_features:
                                self.prediction_features = prediction_features

                        input_size = len(self.prediction_features) + 1
                        output_size = len(self.prediction_features)
                        fc_weight = state_dict.get("fc.weight") if isinstance(state_dict, dict) else None
                        if isinstance(fc_weight, torch.Tensor) and fc_weight.ndim == 2:
                            output_size = fc_weight.shape[0]

                        model = StackedLSTMModel(input_size=input_size, output_size=output_size)
                        try:
                            model.load_state_dict(state_dict)  # type: ignore[arg-type]
                        except Exception as e2:
                            logger.error(
                                "Failed to load LSTM state_dict from checkpoint: %s", e2
                            )
                            model = None

            if model is None:
                raise RuntimeError(
                    f"Unsupported checkpoint type: {type(loaded).__name__}; expected nn.Module, dict with 'model', or state_dict"
                )

            model.to(self.device)
            model.eval()
            self.model = model
        except Exception as e:
            logger.error(f"Failed to load LSTM model from 'ml/lstm_pytorch.pth': {e}")

            class _HoldModel(torch.nn.Module):
                def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
                    try:
                        batch_size = x.shape[0]
                        device = x.device
                    except Exception:
                        batch_size = 1
                        device = self.device if hasattr(self, "device") else torch.device("cpu")
                    logits = torch.tensor(
                        [[0.0, 1.0, 0.0]], dtype=torch.float32, device=device
                    )
                    return logits.repeat(batch_size, 1)

            self.model = _HoldModel()

    @classmethod
    def initialize(cls) -> "ModelService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def get_instance(cls) -> "ModelService":
        if cls._instance is None:
            return cls.initialize()
        return cls._instance

    def _prepare_input(self, candles: List[Any], symbol: Optional[str] = None) -> torch.Tensor:
        if not candles:
            raise ValueError("At least one candle is required for prediction")

        lookback = int(self.lookback) if getattr(self, "lookback", None) else 60
        window = candles[-lookback:]
        if len(window) < lookback:
            first = window[0]
            pad_count = lookback - len(window)
            padding = [first] * pad_count
            window = padding + window

        rows: List[List[float]] = []
        for idx, c in enumerate(window):
            if isinstance(c, dict):
                o = float(c["open"])
                h = float(c["high"])
                l = float(c["low"])
                cl = float(c["close"])
                v = float(c.get("volume", 0.0))
            else:
                o = float(c[0])
                h = float(c[1])
                l = float(c[2])
                cl = float(c[3])
                v = float(c[4]) if len(c) > 4 else 0.0

            if cl != 0.0:
                volatility_index = (h - l) / cl * 100.0
            else:
                volatility_index = 0.0

            decay = math.exp(-float(lookback - 1 - idx) / float(lookback))

            feature_row: List[float] = []
            for name in self.prediction_features:
                if name == "open":
                    feature_row.append(o)
                elif name == "high":
                    feature_row.append(h)
                elif name == "low":
                    feature_row.append(l)
                elif name == "close":
                    feature_row.append(cl)
                elif name == "volume":
                    feature_row.append(v)
                elif name == "volatility_index":
                    feature_row.append(volatility_index)
                elif name == "decay":
                    feature_row.append(decay)
            rows.append(feature_row)

        stock_encoded = 0.0
        if symbol is not None and self.label_encoder is not None:
            try:
                stock_encoded = float(self.label_encoder.transform([symbol])[0])
            except Exception:
                stock_encoded = 0.0

        sequence = [row + [stock_encoded] for row in rows]
        x_np = np.asarray(sequence, dtype=np.float32).reshape(1, lookback, -1)

        if isinstance(self.scalers, dict) and self.scalers.get("X") is not None:
            try:
                scaler_x = self.scalers["X"]
                flat = x_np.reshape(1, -1)
                scaled = scaler_x.transform(flat)
                x_np = scaled.reshape(1, lookback, -1)
            except Exception as e:
                logger.error("Failed to scale input with stored X scaler: %s", e)

        x = torch.tensor(x_np, dtype=torch.float32, device=self.device)
        return x

    def _get_signal_from_output(self, output: Any) -> str:
        if isinstance(output, (list, tuple)):
            logits = output[0]
        else:
            logits = output
        if not torch.is_tensor(logits):
            logits = torch.tensor(logits, dtype=torch.float32, device=self.device)
        if logits.dim() == 1:
            logits = logits.unsqueeze(0)
        probs = torch.softmax(logits, dim=-1)
        index = int(torch.argmax(probs, dim=-1).item())
        mapping = {0: "SELL", 1: "HOLD", 2: "BUY"}
        return mapping.get(index, "HOLD")

    def _compute_prices(
        self,
        signal: str,
        ltp: float,
        orderbook: Dict[str, Any],
        candles: Optional[List[Any]] = None,
    ) -> Dict[str, Optional[float]]:
        bids = orderbook.get("bids") or []
        asks = orderbook.get("asks") or []
        best_bid = orderbook.get("best_bid_price")
        if best_bid is None and bids:
            best_bid = float(bids[0].get("price", 0.0))
        best_ask = orderbook.get("best_ask_price")
        if best_ask is None and asks:
            best_ask = float(asks[0].get("price", 0.0))

        tick_reference = bids if bids else asks
        tick_size: Optional[float] = None
        if isinstance(tick_reference, list) and len(tick_reference) >= 2:
            p0 = float(tick_reference[0].get("price", 0.0))
            p1 = float(tick_reference[1].get("price", 0.0))
            delta = abs(p0 - p1)
            if delta > 0:
                tick_size = delta
        if tick_size is None:
            tick_size = 0.05

        def _round_to_tick(price: float) -> float:
            if tick_size is None or tick_size <= 0:
                return float(price)
            return round(float(price) / tick_size) * tick_size

        # ATR / volatility-based risk sizing
        atr: Optional[float] = None
        if candles and len(candles) >= 2:
            try:
                period = min(14, len(candles) - 1)
                recent = candles[-(period + 1) :]
                trs: List[float] = []

                first = recent[0]
                if isinstance(first, dict):
                    prev_close_val = float(first.get("close"))
                else:
                    prev_close_val = float(first[3])

                for c in recent[1:]:
                    if isinstance(c, dict):
                        high_val = float(c["high"])
                        low_val = float(c["low"])
                        close_val = float(c["close"])
                    else:
                        high_val = float(c[1])
                        low_val = float(c[2])
                        close_val = float(c[3])
                    tr = max(
                        high_val - low_val,
                        abs(high_val - prev_close_val),
                        abs(low_val - prev_close_val),
                    )
                    trs.append(tr)
                    prev_close_val = close_val

                if trs:
                    atr = sum(trs) / float(len(trs))
            except Exception:
                atr = None

        min_risk_points = max(0.002 * float(ltp), 2.0 * tick_size)
        if atr is not None and atr > 0.0:
            risk_points = max(atr, min_risk_points)
        else:
            risk_points = min_risk_points

        reward_multiple = 2.0

        limit_price: Optional[float] = None
        stoploss: Optional[float] = None
        target: Optional[float] = None

        if signal == "BUY":
            # Place buy limit 5 ticks below LTP using tick size inferred from orderbook depth.
            limit_price = float(ltp) - 5 * tick_size
            stoploss = limit_price - risk_points
            target = limit_price + reward_multiple * risk_points
        elif signal == "SELL":
            # Place sell limit 5 ticks above LTP using tick size inferred from orderbook depth.
            limit_price = float(ltp) + 5 * tick_size
            stoploss = limit_price + risk_points
            target = limit_price - reward_multiple * risk_points

        if limit_price is not None:
            limit_price = _round_to_tick(limit_price)
        if stoploss is not None:
            stoploss = _round_to_tick(stoploss)
        if target is not None:
            target = _round_to_tick(target)

        if signal == "HOLD":
            limit_price = None
            stoploss = None
            target = None

        return {
            "limit_price": float(limit_price) if limit_price is not None else None,
            "stoploss": float(stoploss) if stoploss is not None else None,
            "target": float(target) if target is not None else None,
            "best_bid_price": float(best_bid) if best_bid is not None else None,
            "best_ask_price": float(best_ask) if best_ask is not None else None,
            "tick_size": float(tick_size) if tick_size is not None else None,
        }

    def predict(self, candles: List[Any], orderbook: Dict[str, Any], symbol: Optional[str] = None) -> Dict[str, Any]:
        x = self._prepare_input(candles, symbol=symbol)
        with torch.no_grad():
            output = self.model(x)

        last = candles[-1]
        if isinstance(last, dict):
            ltp_value = last.get("close") or last.get("ltp") or last.get("price")
            ltp = float(ltp_value)
        else:
            ltp = float(last[3])

        if torch.is_tensor(output):
            out_tensor = output
        else:
            out_tensor = torch.tensor(output, dtype=torch.float32, device=self.device)
        if out_tensor.dim() == 1:
            out_tensor = out_tensor.unsqueeze(0)

        out_dim = out_tensor.shape[-1]

        if out_dim == 3 and (self.scalers is None or not isinstance(self.scalers, dict)):
            signal = self._get_signal_from_output(out_tensor)
            predicted_close = None
        else:
            out_np = out_tensor.detach().cpu().numpy()
            predicted_features = out_np
            if isinstance(self.scalers, dict) and self.scalers.get("y") is not None:
                try:
                    scaler_y = self.scalers["y"]
                    predicted_features = scaler_y.inverse_transform(out_np)
                except Exception as e:
                    logger.error("Failed to inverse-transform output with stored y scaler: %s", e)

            close_index = 3
            if isinstance(self.prediction_features, list):
                try:
                    close_index = self.prediction_features.index("close")
                except ValueError:
                    close_index = min(close_index, predicted_features.shape[1] - 1)
            predicted_close = float(predicted_features[0][close_index])

            if ltp != 0.0:
                change_pct = (predicted_close - ltp) / ltp * 100.0
            else:
                change_pct = 0.0

            threshold_pct = 0.05
            if change_pct > threshold_pct:
                signal = "BUY"
            elif change_pct < -threshold_pct:
                signal = "SELL"
            else:
                signal = "HOLD"

        prices = self._compute_prices(signal, ltp, orderbook, candles)
        result: Dict[str, Any] = {
            "signal": signal,
            "limit_price": prices["limit_price"],
            "stoploss": prices["stoploss"],
            "target": prices["target"],
            "ltp": ltp,
            "best_bid_price": prices["best_bid_price"],
            "best_ask_price": prices["best_ask_price"],
            "tick_size": prices.get("tick_size"),
        }
        if "predicted_close" not in result:
            result["predicted_close"] = predicted_close if "predicted_close" in locals() else None
        return result

    def resolve_security(self, symbol: str) -> Optional[Dict[str, Any]]:
        return resolve_security_id(symbol)
