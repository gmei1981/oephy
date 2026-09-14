function data_save(filename,data)
fid= fopen(filename,'w');
fprintf(fid,'%d\n',data);
fclose(fid);
end

