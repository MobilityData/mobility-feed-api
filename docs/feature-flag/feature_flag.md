# How to Add a Feature Flag on Firebase

## 1. Go to Remote Config on Firebase

Navigate to the Remote Config section in your Firebase project.
![remote_config](./feature_flag1.png)

## 2. Add a new parameter

Click the "Add parameter" button to create a new parameter.
![remote_config](./feature_flag2.png)

## 3. Create the Feature Flag

Use the new parameter to create a feature flag.
![remote_config](./feature_flag3.png)

Don't forget to publish your changes.
![remote_config](./feature_flag4.png)


## 4. Edit the Feature Flag

You can edit the feature flag by clicking on the pencil editing button. After making your changes, click the "Save" button and publish your changes.
![remote_config](./feature_flag5.png)

## 5. Update `RemoteConfig.ts`

In your code editor, open the `RemoteConfig.ts` file and add `enableMVPSearch` to `defaultRemoteConfigValues`.
![remote_config](./feature_flag6.png)


## 6. Use the Feature Flag in Your Code

You can now use the feature flag in your code to control the behavior of your application.
![remote_config](./feature_flag7.png)
