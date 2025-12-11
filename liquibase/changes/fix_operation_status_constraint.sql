update feed
set operational_status = 'published'
where operational_status is null;

alter table feed
alter column operational_status set not null;