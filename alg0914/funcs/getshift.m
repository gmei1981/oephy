function [left_shift,right_shift,error] = getshift(decimal,max_shift)

if nargin<2
    max_shift = 16;
end

% 计算指数
exp_float = log2(decimal);
% 找到最接近的整数指数
best_exp = round(exp_float);
% 确定左移和右移
if best_exp>=0
    left_shift = best_exp;
    right_shift = 0;
else
    left_shift = 0;
    right_shift = -best_exp;
end
% 检查是否超过最大移位限制
if left_shift>max_shift || right_shift>max_shift
    total_shift = best_exp;
    if total_shift>0
        left_shift = max_shift;
        right_shift = max_shift-total_shift;
    else
        right_shift = max_shift;
        left_shift = max_shift-total_shift;
    end
end

actual_value = 2^(left_shift-right_shift);
error = actual_value - decimal;

end

