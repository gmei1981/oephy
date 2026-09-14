function sat_out = sat(x,width,sign)

if sign==1
    if x > 2^(width-1)-1
         sat_out = 2^(width-1)-1;
    elseif x < -2^(width-1)
         sat_out = -2^(width-1);
    else
        sat_out = x;
    end
else
    if x > 2^width-1
         sat_out = 2^width-1;
    elseif x < 0
         sat_out = 0;
    else
        sat_out = x;
    end
end

end

