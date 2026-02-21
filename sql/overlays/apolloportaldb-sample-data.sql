# Sample Data
# ------------------------------------------------------------
INSERT INTO `App` (`AppId`, `Name`, `OrgId`, `OrgName`, `OwnerName`, `OwnerEmail`)
VALUES
  ('SampleApp', 'Sample App', 'TEST1', '样例部门1', 'apollo', 'apollo@acme.com');

INSERT INTO `AppNamespace` (`Name`, `AppId`, `Format`, `IsPublic`, `Comment`)
VALUES
  ('application', 'SampleApp', 'properties', 0, 'default app namespace');

INSERT INTO `Permission` (`Id`, `PermissionType`, `TargetId`)
VALUES
  (1, 'CreateCluster', 'SampleApp'),
  (2, 'CreateNamespace', 'SampleApp'),
  (3, 'AssignRole', 'SampleApp'),
  (4, 'ModifyNamespace', 'SampleApp+application'),
  (5, 'ReleaseNamespace', 'SampleApp+application');

INSERT INTO `Role` (`Id`, `RoleName`)
VALUES
  (1, 'Master+SampleApp'),
  (2, 'ModifyNamespace+SampleApp+application'),
  (3, 'ReleaseNamespace+SampleApp+application');

INSERT INTO `RolePermission` (`RoleId`, `PermissionId`)
VALUES
  (1, 1),
  (1, 2),
  (1, 3),
  (2, 4),
  (3, 5);

INSERT INTO `UserRole` (`UserId`, `RoleId`)
VALUES
  ('apollo', 1),
  ('apollo', 2),
  ('apollo', 3);
