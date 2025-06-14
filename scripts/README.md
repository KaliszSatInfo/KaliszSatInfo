$$
\text{Score}(L, R) = \text{LOC}(L, R) \times \text{PenaltyFactor}(L) \times \text{SizePenalty}(R)
$$

$$
\text{SizePenalty}(R) = \frac{1}{1 + \left(\frac{S_R}{S_{\max}}\right)^{2.5}}
$$

$$
\text{Score}(L) = \sum_{R} \text{Score}(L, R)
$$

$$
\text{Percentage}(L) = \left( \frac{\text{Score}(L)}{\sum_{L} \text{Score}(L)} \right) \times 100
$$

$$
\text{PenaltyFactor}(L) = \begin{cases}
0.02 & \text{for heavily penalized languages} \\
0.1 & \text{for generated or config languages} \\
1.0 & \text{otherwise}
\end{cases}
$$
