function params = read_cfg_txt(cfg_filename)
fid = fopen(cfg_filename,'r');
if fid == -1
    error('无法打开文件：%s',cfg_filename);
end

params = struct();

while ~feof(fid)
    line = fgetl(fid);
    % 去除首位的空白字符
    line = strtrim(line);
    % 跳过空行
    if isempty(line)
        continue;
    end

    colonIdx = strfind(line,':');
    if isempty(colonIdx)
        warning('行中没有正确的冒号，已跳过：%s',line);
        continue;
    end
    key = strtrim(line(1:colonIdx(1)-1));
    valuestr = strtrim(line(colonIdx(1)+1:end));
    valuestr = regexprep(valuestr,'\s+','');

    numvalue = str2double(valuestr);
    if ~isnan(numvalue) && ~isinf(numvalue)
        value = numvalue;
    else
        value = valuestr;
    end
    params.(key) = value;
end
fclose(fid);
end

